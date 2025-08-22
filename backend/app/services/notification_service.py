from typing import Optional, Dict, Any, List
import logging
import time
from datetime import datetime, timezone, timedelta

from ..models.notification import (
    Notification, NotificationCreate, NotificationUpdate, NotificationSearchFilters, 
    NotificationBulkRead, MessageNotificationCreate, OpportunityNotificationCreate,
    ApplicationNotificationCreate, VerificationNotificationCreate, ModerationNotificationCreate,
    is_valid_notification_type, get_valid_notification_types, get_notification_templates
)
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    'max_notifications_per_user': 1000,
    'rate_limit_window': 3600,  # 1 hour in seconds
    'rate_limit_max': 50,  # Max notifications per hour per user
    'cleanup_days_old': 30,
    'batch_size': 500,  # Firestore batch limit
    'enable_metrics': True,
    'enable_performance_monitoring': False
}


class NotificationService:
    """Notification service for managing user notifications"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.notification_service = DatabaseService("notifications")
        
        # Load configuration with defaults
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.max_notifications_per_user = self.config['max_notifications_per_user']
        self.rate_limit_window = self.config['rate_limit_window']
        self.rate_limit_max = self.config['rate_limit_max']
        self.cleanup_days_old = self.config['cleanup_days_old']
        self.batch_size = self.config['batch_size']
        
        # Only enable features if configured
        self.enable_metrics = self.config.get('enable_metrics', True)
        self.enable_performance_monitoring = self.config.get('enable_performance_monitoring', False)
        
        # Initialize metrics only if enabled
        if self.enable_metrics:
            self.metrics = {
                'notifications_created': 0,
                'notifications_read': 0,
                'notifications_deleted': 0
            }
            # Only add performance metrics if monitoring is enabled
            if self.enable_performance_monitoring:
                self.metrics.update({
                    'total_creation_time': 0.0,
                    'total_read_time': 0.0
                })
        else:
            self.metrics = {}
    
    async def create_notification(self, notification_data: NotificationCreate) -> Dict[str, Any]:
        """Create new notification"""
        # Only track time if performance monitoring is enabled
        start_time = time.time() if self.enable_performance_monitoring else None
        
        try:
            # Input validation is now handled by Pydantic models
            # Check rate limiting
            await self._check_rate_limit(notification_data.user_id)
            
            notification_doc = {
                "user_id": notification_data.user_id,
                "type": notification_data.type,
                "title": notification_data.title,
                "message": notification_data.message,
                "data": notification_data.data or {},
                "is_read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            notification_id = await self.notification_service.create(notification_doc)
            
            # Cleanup old notifications if user has too many
            await self._cleanup_old_notifications_for_user(notification_data.user_id)
            
            # Record metrics only if enabled
            if self.enable_metrics:
                self._record_metric("notifications_created", 1)
                self._record_metric("notifications_created_by_type", notification_data.type, 1)
            
            return await self.get_notification_by_id(notification_id)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise DatabaseError(f"Failed to create notification: {str(e)}")
        finally:
            # Only record performance metrics if monitoring is enabled
            if self.enable_performance_monitoring and start_time is not None:
                duration = time.time() - start_time
                self._record_metric("total_creation_time", duration)
                self._record_metric("notification_creation_duration", duration)
    
    async def get_notification_by_id(self, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID"""
        try:
            if not notification_id:
                raise ValidationError("Notification ID is required")
            
            notification_doc = await self.notification_service.get_by_id(notification_id)
            if not notification_doc:
                raise ResourceNotFoundError("Notification not found", notification_id)
            
            return notification_doc
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting notification by ID {notification_id}: {e}")
            raise DatabaseError(f"Failed to get notification: {str(e)}")
    
    async def get_user_notifications(self, user_id: str, filters: NotificationSearchFilters) -> PaginatedResponse:
        """Get notifications for a user with filters"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            
            firestore_filters = [FieldFilter("user_id", "==", user_id)]
            
            if filters.type:
                # Validation is now handled by Pydantic models
                firestore_filters.append(FieldFilter("type", "==", filters.type))
            
            if filters.unread_only:
                firestore_filters.append(FieldFilter("is_read", "==", False))
            
            notifications = await self.notification_service.query(firestore_filters, filters.limit, filters.offset)
            total_count = await self.notification_service.count(firestore_filters)
            
            return PaginatedResponse(
                count=total_count,
                results=notifications,
                next=f"?limit={filters.limit}&offset={filters.offset + filters.limit}" if filters.offset + filters.limit < total_count else None,
                previous=f"?limit={filters.limit}&offset={max(0, filters.offset - filters.limit)}" if filters.offset > 0 else None
            )
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting notifications for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get notifications: {str(e)}")
    
    async def mark_notification_read(self, notification_id: str, user_id: str) -> Dict[str, Any]:
        """Mark notification as read"""
        # Only track time if performance monitoring is enabled
        start_time = time.time() if self.enable_performance_monitoring else None
        
        try:
            if not notification_id:
                raise ValidationError("Notification ID is required")
            if not user_id:
                raise ValidationError("User ID is required")
            
            notification = await self.get_notification_by_id(notification_id)
            if not notification:
                raise ResourceNotFoundError("Notification not found", notification_id)
            
            if notification["user_id"] != user_id:
                raise AuthorizationError("Not authorized to mark this notification as read")
            
            await self.notification_service.update(notification_id, {"is_read": True})
            
            # Record metrics only if enabled
            if self.enable_metrics:
                self._record_metric("notifications_read", 1)
            
            return await self.get_notification_by_id(notification_id)
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            raise DatabaseError(f"Failed to mark notification as read: {str(e)}")
        finally:
            # Only record performance metrics if monitoring is enabled
            if self.enable_performance_monitoring and start_time is not None:
                duration = time.time() - start_time
                self._record_metric("total_read_time", duration)
                self._record_metric("notification_read_duration", duration)
    
    async def mark_all_notifications_read(self, user_id: str) -> bool:
        """Mark all notifications as read for a user"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            
            # Get all unread notifications for user
            filters = [
                FieldFilter("user_id", "==", user_id),
                FieldFilter("is_read", "==", False)
            ]
            
            unread_notifications = await self.notification_service.query(filters)
            
            # Use batch update for better performance
            if unread_notifications:
                notification_ids = [notification["id"] for notification in unread_notifications]
                await self._batch_update_notifications(notification_ids, {"is_read": True})
                
                # Record metrics only if enabled
                if self.enable_metrics:
                    self._record_metric("notifications_read", len(notification_ids))
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user_id}: {e}")
            raise DatabaseError(f"Failed to mark all notifications as read: {str(e)}")
    
    async def mark_notifications_bulk_read(self, user_id: str, bulk_data: NotificationBulkRead) -> bool:
        """Mark multiple notifications as read"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            
            # Validation is now handled by Pydantic models
            # Validate that all notifications belong to the user
            valid_notification_ids = []
            for notification_id in bulk_data.notification_ids:
                try:
                    notification = await self.get_notification_by_id(notification_id)
                    if notification and notification["user_id"] == user_id:
                        valid_notification_ids.append(notification_id)
                except ResourceNotFoundError:
                    logger.warning(f"Notification {notification_id} not found, skipping")
                    continue
            
            if valid_notification_ids:
                await self._batch_update_notifications(valid_notification_ids, {"is_read": True})
                
                # Record metrics only if enabled
                if self.enable_metrics:
                    self._record_metric("notifications_read", len(valid_notification_ids))
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error marking notifications bulk read for user {user_id}: {e}")
            raise DatabaseError(f"Failed to mark notifications as read: {str(e)}")
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """Delete notification"""
        try:
            if not notification_id:
                raise ValidationError("Notification ID is required")
            if not user_id:
                raise ValidationError("User ID is required")
            
            notification = await self.get_notification_by_id(notification_id)
            if not notification:
                raise ResourceNotFoundError("Notification not found", notification_id)
            
            if notification["user_id"] != user_id:
                raise AuthorizationError("Not authorized to delete this notification")
            
            await self.notification_service.delete(notification_id)
            
            # Record metrics only if enabled
            if self.enable_metrics:
                self._record_metric("notifications_deleted", 1)
            
            return True
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error deleting notification {notification_id}: {e}")
            raise DatabaseError(f"Failed to delete notification: {str(e)}")
    
    async def get_unread_notification_count(self, user_id: str) -> int:
        """Get count of unread notifications for user"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            
            filters = [
                FieldFilter("user_id", "==", user_id),
                FieldFilter("is_read", "==", False)
            ]
            
            unread_count = await self.notification_service.count(filters)
            return unread_count
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting unread notification count for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get unread notification count: {str(e)}")
    
    async def create_message_notification(self, user_id: str, sender_name: str, conversation_id: str) -> Dict[str, Any]:
        """Create notification for new message using template"""
        try:
            # Use the new template model for validation and creation
            message_data = MessageNotificationCreate(
                user_id=user_id,
                sender_name=sender_name,
                conversation_id=conversation_id
            )
            
            # Convert to NotificationCreate using the template
            notification_data = message_data.to_notification_create()
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating message notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create message notification: {str(e)}")
    
    async def create_opportunity_notification(self, user_id: str, opportunity_title: str, opportunity_id: str) -> Dict[str, Any]:
        """Create notification for new opportunity using template"""
        try:
            # Use the new template model for validation and creation
            opportunity_data = OpportunityNotificationCreate(
                user_id=user_id,
                opportunity_title=opportunity_title,
                opportunity_id=opportunity_id
            )
            
            # Convert to NotificationCreate using the template
            notification_data = opportunity_data.to_notification_create()
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating opportunity notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create opportunity notification: {str(e)}")
    
    async def create_application_notification(self, user_id: str, application_status: str, opportunity_title: str) -> Dict[str, Any]:
        """Create notification for application status update using template"""
        try:
            # Use the new template model for validation and creation
            application_data = ApplicationNotificationCreate(
                user_id=user_id,
                application_status=application_status,
                opportunity_title=opportunity_title
            )
            
            # Convert to NotificationCreate using the template
            notification_data = application_data.to_notification_create()
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating application notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create application notification: {str(e)}")
    
    async def create_verification_notification(self, user_id: str, verification_status: str) -> Dict[str, Any]:
        """Create notification for verification status update using template"""
        try:
            # Use the new template model for validation and creation
            verification_data = VerificationNotificationCreate(
                user_id=user_id,
                verification_status=verification_status
            )
            
            # Convert to NotificationCreate using the template
            notification_data = verification_data.to_notification_create()
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating verification notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create verification notification: {str(e)}")
    
    async def create_moderation_notification(self, user_id: str, content_type: str, moderation_status: str) -> Dict[str, Any]:
        """Create notification for content moderation using template"""
        try:
            # Use the new template model for validation and creation
            moderation_data = ModerationNotificationCreate(
                user_id=user_id,
                content_type=content_type,
                moderation_status=moderation_status
            )
            
            # Convert to NotificationCreate using the template
            notification_data = moderation_data.to_notification_create()
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating moderation notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create moderation notification: {str(e)}")
    
    async def cleanup_old_notifications(self, days_old: Optional[int] = None) -> int:
        """Clean up old notifications"""
        try:
            days_old = days_old or self.cleanup_days_old
            if days_old < 1:
                raise ValidationError("Days old must be at least 1")
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Get old notifications
            filters = [FieldFilter("created_at", "<", cutoff_date.isoformat())]
            old_notifications = await self.notification_service.query(filters)
            
            # Delete old notifications in batches
            if old_notifications:
                notification_ids = [notification["id"] for notification in old_notifications]
                await self.notification_service.batch_delete(notification_ids)
                
                # Record metrics only if enabled
                if self.enable_metrics:
                    self._record_metric("notifications_deleted", len(notification_ids))
            
            return len(old_notifications)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            raise DatabaseError(f"Failed to cleanup old notifications: {str(e)}")
    
    async def _check_rate_limit(self, user_id: str) -> None:
        """Check rate limiting for notification creation"""
        try:
            # Get notifications created in the last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(seconds=self.rate_limit_window)
            filters = [
                FieldFilter("user_id", "==", user_id),
                FieldFilter("created_at", ">=", one_hour_ago.isoformat())
            ]
            
            recent_count = await self.notification_service.count(filters)
            if recent_count >= self.rate_limit_max:
                raise ValidationError(f"Rate limit exceeded. Maximum {self.rate_limit_max} notifications per hour.")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.warning(f"Rate limit check failed for user {user_id}: {e}")
            # Don't fail the main operation due to rate limit check failure
            # but log it as a warning for monitoring
    
    async def _cleanup_old_notifications_for_user(self, user_id: str) -> None:
        """Clean up old notifications for a specific user"""
        try:
            filters = [FieldFilter("user_id", "==", user_id)]
            user_notifications = await self.notification_service.query(filters)
            
            if len(user_notifications) > self.max_notifications_per_user:
                # Sort by creation date and keep the most recent
                sorted_notifications = sorted(user_notifications, key=lambda x: x.get("created_at", ""), reverse=True)
                notifications_to_delete = sorted_notifications[self.max_notifications_per_user:]
                
                if notifications_to_delete:
                    notification_ids = [notification["id"] for notification in notifications_to_delete]
                    await self.notification_service.batch_delete(notification_ids)
                    
                    # Record metrics only if enabled
                    if self.enable_metrics:
                        self._record_metric("notifications_deleted", len(notification_ids))
                    
        except Exception as e:
            logger.warning(f"Cleanup of old notifications failed for user {user_id}: {e}")
            # Don't fail the main operation due to cleanup failure
            # but log it as a warning for monitoring
    
    async def _batch_update_notifications(self, notification_ids: List[str], update_data: Dict[str, Any]) -> None:
        """Update multiple notifications in a true batch operation"""
        try:
            if not notification_ids:
                return
                
            # Use Firestore batch operations for better performance
            batch = self.notification_service.db.batch()
            
            # Process in chunks to respect Firestore batch limits
            for i in range(0, len(notification_ids), self.batch_size):
                chunk = notification_ids[i:i + self.batch_size]
                
                for notification_id in chunk:
                    doc_ref = self.notification_service.collection.document(notification_id)
                    batch.update(doc_ref, update_data)
                
                # Commit this chunk
                batch.commit()
                
                # Create new batch for next chunk if needed
                if i + self.batch_size < len(notification_ids):
                    batch = self.notification_service.db.batch()
                    
        except Exception as e:
            logger.error(f"Error in batch update notifications: {e}")
            raise DatabaseError(f"Failed to batch update notifications: {str(e)}")
    
    def _record_metric(self, metric_name: str, increment: int = 1) -> None:
        """Record simple metrics with minimal overhead"""
        if not self.enable_metrics:
            return
        
        try:
            if metric_name in self.metrics:
                self.metrics[metric_name] += increment
            else:
                self.metrics[metric_name] = increment
        except Exception as e:
            logger.warning(f"Failed to record metric {metric_name}: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics for monitoring"""
        return self.metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset metrics (useful for testing or periodic resets)"""
        if not self.enable_metrics:
            return
            
        self.metrics = {
            'notifications_created': 0,
            'notifications_read': 0,
            'notifications_deleted': 0
        }
        
        # Only add performance metrics if monitoring is enabled
        if self.enable_performance_monitoring:
            self.metrics.update({
                'total_creation_time': 0.0,
                'total_read_time': 0.0
            })
    
    # Template utility methods (now delegate to models)
    def is_valid_notification_type(self, notification_type: str) -> bool:
        """Check if notification type is valid (delegates to model)"""
        return is_valid_notification_type(notification_type)
    
    def get_valid_notification_types(self) -> List[str]:
        """Get list of valid notification types (delegates to model)"""
        return get_valid_notification_types()
    
    def get_templates(self):
        """Get notification templates (delegates to model)"""
        return get_notification_templates() 