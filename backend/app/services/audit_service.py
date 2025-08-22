from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
import asyncio
from enum import Enum
from firebase_admin.firestore import FieldFilter

from .database_service import DatabaseService

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Standard audit actions"""
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SOFT_DELETE = "SOFT_DELETE"
    RESTORE = "RESTORE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    BULK_OPERATION = "BULK_OPERATION"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    SEARCH = "SEARCH"
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    SHARE = "SHARE"
    VERIFY = "VERIFY"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SUSPEND = "SUSPEND"
    ACTIVATE = "ACTIVATE"
    DEACTIVATE = "DEACTIVATE"


class AuditLevel(Enum):
    """Audit logging levels"""
    LOW = "LOW"      # Basic operations (CRUD)
    MEDIUM = "MEDIUM"  # Sensitive operations (permissions, auth)
    HIGH = "HIGH"    # Critical operations (deletions, bulk operations)
    CRITICAL = "CRITICAL"  # Security events, compliance operations


@dataclass
class AuditEvent:
    """Audit event data structure"""
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: datetime
    level: AuditLevel = AuditLevel.MEDIUM
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditService:
    """Centralized audit logging service for the entire application"""
    
    def __init__(self):
        self.audit_db = DatabaseService("audit_logs")
        self.config = {
            "retention_days": 90,  # Keep logs for 90 days
            "batch_size": 100,     # Process audit events in batches
            "async_processing": True,
            "enable_compression": False,
            "log_levels": [level.value for level in AuditLevel],
            "sensitive_fields": ["password", "token", "secret", "key", "credential"],
            "max_event_size": 1024 * 1024,  # 1MB max event size
        }
        
        # Initialize audit categories
        self._init_audit_categories()
    
    def _init_audit_categories(self):
        """Initialize audit categories and their configurations"""
        self.audit_categories = {
            "user_management": {
                "level": AuditLevel.HIGH,
                "required_fields": ["user_id", "action", "resource_type", "resource_id"],
                "sensitive_operations": ["DELETE", "PERMISSION_CHANGE", "PASSWORD_CHANGE"]
            },
            "athlete_profiles": {
                "level": AuditLevel.MEDIUM,
                "required_fields": ["user_id", "action", "resource_type", "resource_id"],
                "sensitive_operations": ["DELETE", "BULK_OPERATION"]
            },
            "media_management": {
                "level": AuditLevel.MEDIUM,
                "required_fields": ["user_id", "action", "resource_type", "resource_id"],
                "sensitive_operations": ["UPLOAD", "DOWNLOAD", "SHARE"]
            },
            "authentication": {
                "level": AuditLevel.HIGH,
                "required_fields": ["user_id", "action", "ip_address", "timestamp"],
                "sensitive_operations": ["LOGIN", "LOGIN_FAILED", "PASSWORD_CHANGE"]
            },
            "opportunities": {
                "level": AuditLevel.MEDIUM,
                "required_fields": ["user_id", "action", "resource_type", "resource_id"],
                "sensitive_operations": ["APPROVE", "REJECT", "SUSPEND"]
            }
        }
    
    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask sensitive data from audit logs"""
        if not data:
            return data
        
        sanitized = data.copy()
        for key, value in sanitized.items():
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_sensitive_data(value)
            elif isinstance(value, str) and any(sensitive in key.lower() for sensitive in self.config["sensitive_fields"]):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_sensitive_data(item) if isinstance(item, dict) else item for item in value]
        
        return sanitized
    
    def _validate_audit_event(self, event: AuditEvent) -> bool:
        """Validate audit event before logging"""
        try:
            # Check required fields
            if not event.user_id or not event.action or not event.resource_type or not event.resource_id:
                logger.warning(f"Invalid audit event: missing required fields")
                return False
            
            # Check event size
            event_size = len(str(asdict(event)))
            if event_size > self.config["max_event_size"]:
                logger.warning(f"Audit event too large: {event_size} bytes")
                return False
            
            # Check if action is valid
            try:
                AuditAction(event.action)
            except ValueError:
                logger.warning(f"Invalid audit action: {event.action}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating audit event: {e}")
            return False
    
    async def log_event(self, event: AuditEvent) -> Optional[str]:
        """Log a single audit event"""
        try:
            # Validate event
            if not self._validate_audit_event(event):
                return None
            
            # Sanitize sensitive data
            if event.before_state:
                event.before_state = self._sanitize_sensitive_data(event.before_state)
            if event.after_state:
                event.after_state = self._sanitize_sensitive_data(event.after_state)
            if event.details:
                event.details = self._sanitize_sensitive_data(event.details)
            
            # Prepare audit document
            audit_doc = asdict(event)
            audit_doc["timestamp"] = event.timestamp.isoformat()
            audit_doc["created_at"] = datetime.utcnow().isoformat()
            audit_doc["level"] = event.level.value
            
            # Add metadata
            audit_doc["version"] = "1.0"
            audit_doc["environment"] = "production"  # Could be configurable
            audit_doc["service"] = "audit_service"
            
            # Create audit log entry
            event_id = await self.audit_db.create(audit_doc)
            
            logger.debug(f"Audit event logged: {event_id} - {event.action} on {event.resource_type}")
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Don't raise - audit logging should not break main functionality
            return None
    
    async def log_batch_events(self, events: List[AuditEvent]) -> Dict[str, Any]:
        """Log multiple audit events in batch"""
        try:
            if not events:
                return {"successful": 0, "failed": 0, "errors": []}
            
            results = {
                "successful": 0,
                "failed": 0,
                "errors": [],
                "total": len(events)
            }
            
            # Process events in batches
            batch_size = self.config["batch_size"]
            for i in range(0, len(events), batch_size):
                batch = events[i:i + batch_size]
                
                for event in batch:
                    try:
                        event_id = await self.log_event(event)
                        if event_id:
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                            results["errors"].append(f"Failed to log event: {event.action}")
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"Error logging event: {str(e)}")
            
            logger.info(f"Batch audit logging completed: {results['successful']} successful, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"Failed to log batch audit events: {e}")
            return {"successful": 0, "failed": len(events), "errors": [str(e)], "total": len(events)}
    
    async def get_user_activity(self, user_id: str, limit: int = 100, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               actions: Optional[List[str]] = None,
                               resource_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all activity for a specific user within a date range"""
        try:
            filters = [FieldFilter("user_id", "==", user_id)]
            
            if start_date:
                filters.append(FieldFilter("timestamp", ">=", start_date.isoformat()))
            if end_date:
                filters.append(FieldFilter("timestamp", "<=", end_date.isoformat()))
            if actions:
                filters.append(FieldFilter("action", "in", actions))
            if resource_types:
                filters.append(FieldFilter("resource_type", "in", resource_types))
            
            return await self.audit_db.query(
                filters, 
                limit=limit, 
                order_by="timestamp", 
                direction="desc"
            )
            
        except Exception as e:
            logger.error(f"Failed to get user activity for {user_id}: {e}")
            raise
    
    async def get_resource_history(self, resource_type: str, resource_id: str,
                                 include_deleted: bool = False,
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Get complete history of changes for a specific resource"""
        try:
            filters = [
                FieldFilter("resource_type", "==", resource_type),
                FieldFilter("resource_id", "==", resource_id)
            ]
            
            if not include_deleted:
                filters.append(FieldFilter("action", "!=", "DELETE"))
            
            return await self.audit_db.query(
                filters, 
                limit=limit,
                order_by="timestamp", 
                direction="asc"
            )
            
        except Exception as e:
            logger.error(f"Failed to get resource history: {e}")
            raise
    
    async def get_suspicious_activity(self, time_window_hours: int = 24,
                                    threshold: int = 10,
                                    min_level: AuditLevel = AuditLevel.MEDIUM) -> List[Dict[str, Any]]:
        """Get potentially suspicious activity patterns"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            
            filters = [
                FieldFilter("timestamp", ">=", cutoff_time.isoformat()),
                FieldFilter("level", "in", [level.value for level in AuditLevel if level.value >= min_level.value])
            ]
            
            recent_events = await self.audit_db.query(filters)
            
            # Analyze patterns
            user_action_counts = {}
            suspicious_events = []
            
            for event in recent_events:
                user_key = f"{event['user_id']}_{event['action']}"
                user_action_counts[user_key] = user_action_counts.get(user_key, 0) + 1
                
                # Flag suspicious patterns
                if user_action_counts[user_key] > threshold:
                    suspicious_events.append({
                        **event,
                        "suspicious_reason": f"High frequency: {user_action_counts[user_key]} actions",
                        "frequency_count": user_action_counts[user_key]
                    })
            
            return suspicious_events
            
        except Exception as e:
            logger.error(f"Failed to get suspicious activity: {e}")
            raise
    
    async def get_audit_summary(self, start_date: datetime, end_date: datetime,
                               group_by: str = "action") -> Dict[str, Any]:
        """Get summary statistics of audit events"""
        try:
            filters = [
                FieldFilter("timestamp", ">=", start_date.isoformat()),
                FieldFilter("timestamp", "<=", end_date.isoformat())
            ]
            
            events = await self.audit_db.query(filters)
            
            summary = {
                "total_events": len(events),
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "grouped_data": {},
                "level_distribution": {},
                "user_activity": {}
            }
            
            # Group by specified field
            for event in events:
                group_value = event.get(group_by, "unknown")
                if group_value not in summary["grouped_data"]:
                    summary["grouped_data"][group_value] = 0
                summary["grouped_data"][group_value] += 1
                
                # Level distribution
                level = event.get("level", "unknown")
                if level not in summary["level_distribution"]:
                    summary["level_distribution"][level] = 0
                summary["level_distribution"][level] += 1
                
                # User activity
                user_id = event.get("user_id", "unknown")
                if user_id not in summary["user_activity"]:
                    summary["user_activity"][user_id] = 0
                summary["user_activity"][user_id] += 1
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get audit summary: {e}")
            raise
    
    async def cleanup_old_logs(self, days_to_keep: Optional[int] = None) -> int:
        """Clean up audit logs older than specified days"""
        try:
            days = days_to_keep or self.config["retention_days"]
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            filters = [FieldFilter("timestamp", "<", cutoff_date.isoformat())]
            old_logs = await self.audit_db.query(filters)
            
            deleted_count = 0
            for log in old_logs:
                try:
                    await self.audit_db.delete(log["id"])
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete old audit log {log['id']}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old audit logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            raise
    
    async def export_audit_logs(self, start_date: datetime, end_date: datetime,
                               resource_type: Optional[str] = None,
                               user_id: Optional[str] = None,
                               actions: Optional[List[str]] = None,
                               levels: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Export audit logs for compliance reporting"""
        try:
            filters = [
                FieldFilter("timestamp", ">=", start_date.isoformat()),
                FieldFilter("timestamp", "<=", end_date.isoformat())
            ]
            
            if resource_type:
                filters.append(FieldFilter("resource_type", "==", resource_type))
            if user_id:
                filters.append(FieldFilter("user_id", "==", user_id))
            if actions:
                filters.append(FieldFilter("action", "in", actions))
            if levels:
                filters.append(FieldFilter("level", "in", levels))
            
            return await self.audit_db.query(filters, order_by="timestamp", direction="asc")
            
        except Exception as e:
            logger.error(f"Failed to export audit logs: {e}")
            raise
    
    async def get_compliance_report(self, start_date: datetime, end_date: datetime,
                                   report_type: str = "general") -> Dict[str, Any]:
        """Generate compliance reports for different regulations"""
        try:
            events = await self.export_audit_logs(start_date, end_date)
            
            report = {
                "report_type": report_type,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "generated_at": datetime.utcnow().isoformat(),
                "total_events": len(events),
                "compliance_metrics": {},
                "risk_indicators": [],
                "recommendations": []
            }
            
            # Calculate compliance metrics based on report type
            if report_type == "gdpr":
                report["compliance_metrics"] = self._calculate_gdpr_metrics(events)
            elif report_type == "sox":
                report["compliance_metrics"] = self._calculate_sox_metrics(events)
            elif report_type == "hipaa":
                report["compliance_metrics"] = self._calculate_hipaa_metrics(events)
            else:
                report["compliance_metrics"] = self._calculate_general_metrics(events)
            
            # Identify risk indicators
            report["risk_indicators"] = self._identify_risk_indicators(events)
            
            # Generate recommendations
            report["recommendations"] = self._generate_recommendations(report["compliance_metrics"])
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise
    
    def _calculate_gdpr_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate GDPR compliance metrics"""
        metrics = {
            "data_access_events": 0,
            "data_modification_events": 0,
            "data_deletion_events": 0,
            "user_consent_events": 0,
            "data_export_events": 0
        }
        
        for event in events:
            action = event.get("action", "")
            if action in ["READ", "SEARCH"]:
                metrics["data_access_events"] += 1
            elif action in ["CREATE", "UPDATE"]:
                metrics["data_modification_events"] += 1
            elif action in ["DELETE", "SOFT_DELETE"]:
                metrics["data_deletion_events"] += 1
            elif action == "EXPORT":
                metrics["data_export_events"] += 1
        
        return metrics
    
    def _calculate_sox_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate SOX compliance metrics"""
        metrics = {
            "financial_data_access": 0,
            "permission_changes": 0,
            "system_access": 0,
            "data_integrity_events": 0
        }
        
        for event in events:
            action = event.get("action", "")
            resource_type = event.get("resource_type", "")
            
            if action == "PERMISSION_CHANGE":
                metrics["permission_changes"] += 1
            elif resource_type in ["financial_record", "transaction", "account"]:
                metrics["financial_data_access"] += 1
            elif action in ["LOGIN", "LOGOUT"]:
                metrics["system_access"] += 1
        
        return metrics
    
    def _calculate_hipaa_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate HIPAA compliance metrics"""
        metrics = {
            "phi_access_events": 0,
            "phi_modification_events": 0,
            "phi_deletion_events": 0,
            "authentication_events": 0,
            "authorization_events": 0
        }
        
        for event in events:
            action = event.get("action", "")
            resource_type = event.get("resource_type", "")
            
            if resource_type in ["patient_record", "medical_record", "health_data"]:
                if action in ["READ", "SEARCH"]:
                    metrics["phi_access_events"] += 1
                elif action in ["CREATE", "UPDATE"]:
                    metrics["phi_modification_events"] += 1
                elif action in ["DELETE", "SOFT_DELETE"]:
                    metrics["phi_deletion_events"] += 1
            
            if action in ["LOGIN", "LOGOUT", "LOGIN_FAILED"]:
                metrics["authentication_events"] += 1
            elif action == "PERMISSION_CHANGE":
                metrics["authorization_events"] += 1
        
        return metrics
    
    def _calculate_general_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate general audit metrics"""
        metrics = {
            "total_events": len(events),
            "unique_users": len(set(event.get("user_id") for event in events if event.get("user_id"))),
            "unique_resources": len(set(f"{event.get('resource_type')}:{event.get('resource_id')}" for event in events)),
            "action_distribution": {},
            "level_distribution": {}
        }
        
        for event in events:
            action = event.get("action", "unknown")
            level = event.get("level", "unknown")
            
            metrics["action_distribution"][action] = metrics["action_distribution"].get(action, 0) + 1
            metrics["level_distribution"][level] = metrics["level_distribution"].get(level, 0) + 1
        
        return metrics
    
    def _identify_risk_indicators(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify potential risk indicators in audit events"""
        risk_indicators = []
        
        # High frequency actions
        action_counts = {}
        for event in events:
            action = event.get("action", "")
            action_counts[action] = action_counts.get(action, 0) + 1
        
        for action, count in action_counts.items():
            if count > 50:  # Threshold for high frequency
                risk_indicators.append({
                    "type": "high_frequency_action",
                    "action": action,
                    "count": count,
                    "risk_level": "medium",
                    "description": f"High frequency of {action} actions"
                })
        
        # Failed operations
        failed_events = [e for e in events if "FAILED" in e.get("action", "")]
        if failed_events:
            risk_indicators.append({
                "type": "failed_operations",
                "count": len(failed_events),
                "risk_level": "high",
                "description": f"Multiple failed operations detected"
            })
        
        # Unusual access patterns
        user_access_patterns = {}
        for event in events:
            user_id = event.get("user_id", "")
            if user_id not in user_access_patterns:
                user_access_patterns[user_id] = []
            user_access_patterns[user_id].append(event.get("timestamp", ""))
        
        for user_id, timestamps in user_access_patterns.items():
            if len(timestamps) > 100:  # High activity user
                risk_indicators.append({
                    "type": "high_activity_user",
                    "user_id": user_id,
                    "activity_count": len(timestamps),
                    "risk_level": "low",
                    "description": f"User {user_id} has high activity level"
                })
        
        return risk_indicators
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on compliance metrics"""
        recommendations = []
        
        # General recommendations
        if metrics.get("total_events", 0) > 10000:
            recommendations.append("Consider implementing log rotation and archiving for better performance")
        
        if metrics.get("failed_operations", 0) > 100:
            recommendations.append("Investigate failed operations to identify system issues or security concerns")
        
        if metrics.get("high_frequency_actions", 0) > 0:
            recommendations.append("Review high-frequency actions for potential automation opportunities")
        
        # GDPR specific
        if "data_access_events" in metrics and metrics["data_access_events"] > 1000:
            recommendations.append("Implement data access controls and monitoring for GDPR compliance")
        
        # SOX specific
        if "permission_changes" in metrics and metrics["permission_changes"] > 50:
            recommendations.append("Review permission change procedures for SOX compliance")
        
        # HIPAA specific
        if "phi_access_events" in metrics and metrics["phi_access_events"] > 500:
            recommendations.append("Implement PHI access monitoring and controls for HIPAA compliance")
        
        if not recommendations:
            recommendations.append("Current audit metrics indicate good compliance practices")
        
        return recommendations 