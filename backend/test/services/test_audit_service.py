import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.audit_service import (
    AuditService, AuditEvent, AuditAction, AuditLevel
)


@pytest.fixture
def mock_audit_service():
    """Mock audit service for testing"""
    with patch('app.services.audit_service.DatabaseService') as mock_db:
        service = AuditService()
        service.audit_db = mock_db.return_value
        yield service


@pytest.fixture
def sample_audit_event():
    """Sample audit event for testing"""
    return AuditEvent(
        user_id="user123",
        action="CREATE",
        resource_type="athlete_profile",
        resource_id="profile123",
        timestamp=datetime.utcnow(),
        level=AuditLevel.MEDIUM,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        details={"profile_data": {"name": "John Doe"}},
        before_state={},
        after_state={"id": "profile123", "name": "John Doe"}
    )


class TestAuditService:
    """Test cases for AuditService"""
    
    def test_audit_service_initialization(self, mock_audit_service):
        """Test audit service initialization"""
        assert mock_audit_service.audit_db is not None
        assert mock_audit_service.config["retention_days"] == 90
        assert mock_audit_service.config["batch_size"] == 100
        assert mock_audit_service.config["async_processing"] is True
    
    def test_audit_categories_initialization(self, mock_audit_service):
        """Test audit categories are properly initialized"""
        assert "user_management" in mock_audit_service.audit_categories
        assert "athlete_profiles" in mock_audit_service.audit_categories
        assert "media_management" in mock_audit_service.audit_categories
        assert "authentication" in mock_audit_service.audit_categories
        assert "opportunities" in mock_audit_service.audit_categories
    
    def test_audit_action_enum_values(self):
        """Test audit action enum values"""
        assert AuditAction.CREATE.value == "CREATE"
        assert AuditAction.UPDATE.value == "UPDATE"
        assert AuditAction.DELETE.value == "DELETE"
        assert AuditAction.LOGIN.value == "LOGIN"
        assert AuditAction.LOGIN_FAILED.value == "LOGIN_FAILED"
    
    def test_audit_level_enum_values(self):
        """Test audit level enum values"""
        assert AuditLevel.LOW.value == "LOW"
        assert AuditLevel.MEDIUM.value == "MEDIUM"
        assert AuditLevel.HIGH.value == "HIGH"
        assert AuditLevel.CRITICAL.value == "CRITICAL"
    
    def test_audit_event_dataclass(self, sample_audit_event):
        """Test audit event dataclass structure"""
        assert sample_audit_event.user_id == "user123"
        assert sample_audit_event.action == "CREATE"
        assert sample_audit_event.resource_type == "athlete_profile"
        assert sample_audit_event.resource_id == "profile123"
        assert sample_audit_event.level == AuditLevel.MEDIUM
        assert sample_audit_event.ip_address == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_log_event_success(self, mock_audit_service, sample_audit_event):
        """Test successful audit event logging"""
        mock_audit_service.audit_db.create.return_value = "audit123"
        
        result = await mock_audit_service.log_event(sample_audit_event)
        
        assert result == "audit123"
        mock_audit_service.audit_db.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_event_validation_failure(self, mock_audit_service):
        """Test audit event validation failure"""
        invalid_event = AuditEvent(
            user_id="",  # Invalid: empty user_id
            action="CREATE",
            resource_type="athlete_profile",
            resource_id="profile123",
            timestamp=datetime.utcnow()
        )
        
        result = await mock_audit_service.log_event(invalid_event)
        
        assert result is None
        mock_audit_service.audit_db.create.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_log_event_database_error(self, mock_audit_service, sample_audit_event):
        """Test audit event logging with database error"""
        mock_audit_service.audit_db.create.side_effect = Exception("Database error")
        
        result = await mock_audit_service.log_event(sample_audit_event)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_log_batch_events_success(self, mock_audit_service):
        """Test successful batch audit event logging"""
        events = [
            AuditEvent(
                user_id="user1",
                action="CREATE",
                resource_type="athlete_profile",
                resource_id="profile1",
                timestamp=datetime.utcnow()
            ),
            AuditEvent(
                user_id="user2",
                action="UPDATE",
                resource_type="athlete_profile",
                resource_id="profile2",
                timestamp=datetime.utcnow()
            )
        ]
        
        mock_audit_service.audit_db.create.side_effect = ["audit1", "audit2"]
        
        result = await mock_audit_service.log_batch_events(events)
        
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["total"] == 2
        assert len(result["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_log_batch_events_partial_failure(self, mock_audit_service):
        """Test batch audit event logging with partial failures"""
        events = [
            AuditEvent(
                user_id="user1",
                action="CREATE",
                resource_type="athlete_profile",
                resource_id="profile1",
                timestamp=datetime.utcnow()
            ),
            AuditEvent(
                user_id="user2",
                action="UPDATE",
                resource_type="athlete_profile",
                resource_id="profile2",
                timestamp=datetime.utcnow()
            )
        ]
        
        mock_audit_service.audit_db.create.side_effect = ["audit1", Exception("Database error")]
        
        result = await mock_audit_service.log_batch_events(events)
        
        assert result["successful"] == 1
        assert result["failed"] == 1
        assert result["total"] == 2
        assert len(result["errors"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_user_activity_success(self, mock_audit_service):
        """Test getting user activity successfully"""
        mock_events = [
            {"id": "audit1", "action": "CREATE", "timestamp": "2024-01-01T00:00:00"},
            {"id": "audit2", "action": "UPDATE", "timestamp": "2024-01-02T00:00:00"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_events
        
        result = await mock_audit_service.get_user_activity("user123", limit=10)
        
        assert len(result) == 2
        assert result[0]["action"] == "CREATE"
        assert result[1]["action"] == "UPDATE"
    
    @pytest.mark.asyncio
    async def test_get_resource_history_success(self, mock_audit_service):
        """Test getting resource history successfully"""
        mock_history = [
            {"id": "audit1", "action": "CREATE", "timestamp": "2024-01-01T00:00:00"},
            {"id": "audit2", "action": "UPDATE", "timestamp": "2024-01-02T00:00:00"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_history
        
        result = await mock_audit_service.get_resource_history("athlete_profile", "profile123")
        
        assert len(result) == 2
        assert result[0]["action"] == "CREATE"
        assert result[1]["action"] == "UPDATE"
    
    @pytest.mark.asyncio
    async def test_get_suspicious_activity_success(self, mock_audit_service):
        """Test getting suspicious activity successfully"""
        mock_events = [
            {"id": "audit1", "user_id": "user1", "action": "CREATE", "timestamp": "2024-01-01T00:00:00", "level": "MEDIUM"},
            {"id": "audit2", "user_id": "user1", "action": "CREATE", "timestamp": "2024-01-01T01:00:00", "level": "MEDIUM"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_events
        
        result = await mock_audit_service.get_suspicious_activity(time_window_hours=24, threshold=1)
        
        assert len(result) > 0
        assert "suspicious_reason" in result[0]
    
    @pytest.mark.asyncio
    async def test_get_audit_summary_success(self, mock_audit_service):
        """Test getting audit summary successfully"""
        mock_events = [
            {"id": "audit1", "action": "CREATE", "level": "MEDIUM", "user_id": "user1"},
            {"id": "audit2", "action": "UPDATE", "level": "MEDIUM", "user_id": "user2"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_events
        
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        result = await mock_audit_service.get_audit_summary(start_date, end_date)
        
        assert result["total_events"] == 2
        assert "grouped_data" in result
        assert "level_distribution" in result
        assert "user_activity" in result
    
    @pytest.mark.asyncio
    async def test_export_audit_logs_success(self, mock_audit_service):
        """Test exporting audit logs successfully"""
        mock_logs = [
            {"id": "audit1", "action": "CREATE", "timestamp": "2024-01-01T00:00:00"},
            {"id": "audit2", "action": "UPDATE", "timestamp": "2024-01-02T00:00:00"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_logs
        
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        result = await mock_audit_service.export_audit_logs(start_date, end_date)
        
        assert len(result) == 2
        assert result[0]["action"] == "CREATE"
        assert result[1]["action"] == "UPDATE"
    
    @pytest.mark.asyncio
    async def test_cleanup_old_logs_success(self, mock_audit_service):
        """Test cleaning up old audit logs successfully"""
        mock_old_logs = [
            {"id": "old1", "timestamp": "2023-01-01T00:00:00"},
            {"id": "old2", "timestamp": "2023-01-02T00:00:00"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_old_logs
        mock_audit_service.audit_db.delete.return_value = None
        
        result = await mock_audit_service.cleanup_old_logs(days_to_keep=30)
        
        assert result == 2
        assert mock_audit_service.audit_db.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_compliance_report_gdpr(self, mock_audit_service):
        """Test generating GDPR compliance report"""
        mock_events = [
            {"id": "audit1", "action": "READ", "timestamp": "2024-01-01T00:00:00"},
            {"id": "audit2", "action": "UPDATE", "timestamp": "2024-01-02T00:00:00"},
            {"id": "audit3", "action": "DELETE", "timestamp": "2024-01-03T00:00:00"}
        ]
        
        mock_audit_service.audit_db.query.return_value = mock_events
        
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        result = await mock_audit_service.get_compliance_report(start_date, end_date, "gdpr")
        
        assert result["report_type"] == "gdpr"
        assert "compliance_metrics" in result
        assert "risk_indicators" in result
        assert "recommendations" in result
    
    def test_sanitize_sensitive_data(self, mock_audit_service):
        """Test sanitizing sensitive data"""
        test_data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com",
            "token": "abc123",
            "nested": {
                "api_key": "xyz789",
                "normal_field": "value"
            }
        }
        
        sanitized = mock_audit_service._sanitize_sensitive_data(test_data)
        
        assert sanitized["username"] == "john_doe"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["email"] == "john@example.com"
        assert sanitized["token"] == "[REDACTED]"
        assert sanitized["nested"]["api_key"] == "[REDACTED]"
        assert sanitized["nested"]["normal_field"] == "value"
    
    def test_validate_audit_event_valid(self, mock_audit_service, sample_audit_event):
        """Test validating valid audit event"""
        result = mock_audit_service._validate_audit_event(sample_audit_event)
        assert result is True
    
    def test_validate_audit_event_invalid(self, mock_audit_service):
        """Test validating invalid audit event"""
        invalid_event = AuditEvent(
            user_id="",  # Invalid: empty user_id
            action="CREATE",
            resource_type="athlete_profile",
            resource_id="profile123",
            timestamp=datetime.utcnow()
        )
        
        result = mock_audit_service._validate_audit_event(invalid_event)
        assert result is False 