from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timezone, timedelta

from ..models.notification import Notification, NotificationCreate, NotificationUpdate, NotificationSearchFilters, NotificationBulkRead
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError

logger = logging.getLogger(__name__)


class NotificationService:
    """Notification service for managing user notifications"""
    
    def __init__(self):
        self.notification_service = DatabaseService("notifications")
        self.max_notifications_per_user = 1000  # Prevent spam
        self.rate_limit_window = 3600  # 1 hour in seconds
        self.rate_limit_max = 50  # Max notifications per hour per user
    
    async def create_notification(self, notification_data: NotificationCreate) -> Dict[str, Any]:
        """Create new notification"""
        try:
            # Input validation
            if not notification_data.user_id:
                raise ValidationError("User ID is required")
            if not notification_data.type:
                raise ValidationError("Notification type is required")
            if not notification_data.title or not notification_data.title.strip():
                raise ValidationError("Notification title is required")
            if not notification_data.message or not notification_data.message.strip():
                raise ValidationError("Notification message is required")
            
            # Validate notification type
            valid_types = ["message", "opportunity", "application", "verification", "moderation"]
            if notification_data.type not in valid_types:
                raise ValidationError(f"Invalid notification type. Must be one of: {valid_types}")
            
            # Check rate limiting
            await self._check_rate_limit(notification_data.user_id)
            
            notification_doc = {
                "user_id": notification_data.user_id,
                "type": notification_data.type,
                "title": notification_data.title.strip(),
                "message": notification_data.message.strip(),
                "data": notification_data.data or {},
                "is_read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            notification_id = await self.notification_service.create(notification_doc)
            
            # Cleanup old notifications if user has too many
            await self._cleanup_old_notifications_for_user(notification_data.user_id)
            
            return await self.get_notification_by_id(notification_id)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise DatabaseError(f"Failed to create notification: {str(e)}")
    
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
                valid_types = ["message", "opportunity", "application", "verification", "moderation"]
                if filters.type not in valid_types:
                    raise ValidationError(f"Invalid notification type. Must be one of: {valid_types}")
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
            
            return await self.get_notification_by_id(notification_id)
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            raise DatabaseError(f"Failed to mark notification as read: {str(e)}")
    
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
            if not bulk_data.notification_ids:
                raise ValidationError("Notification IDs are required")
            
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
        """Create notification for new message"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            if not sender_name or not sender_name.strip():
                raise ValidationError("Sender name is required")
            if not conversation_id:
                raise ValidationError("Conversation ID is required")
            
            notification_data = NotificationCreate(
                user_id=user_id,
                type="message",
                title="New Message",
                message=f"You received a new message from {sender_name.strip()}",
                data={"conversation_id": conversation_id}
            )
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating message notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create message notification: {str(e)}")
    
    async def create_opportunity_notification(self, user_id: str, opportunity_title: str, opportunity_id: str) -> Dict[str, Any]:
        """Create notification for new opportunity"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            if not opportunity_title or not opportunity_title.strip():
                raise ValidationError("Opportunity title is required")
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required")
            
            notification_data = NotificationCreate(
                user_id=user_id,
                type="opportunity",
                title="New Opportunity",
                message=f"New opportunity available: {opportunity_title.strip()}",
                data={"opportunity_id": opportunity_id}
            )
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating opportunity notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create opportunity notification: {str(e)}")
    
    async def create_application_notification(self, user_id: str, application_status: str, opportunity_title: str) -> Dict[str, Any]:
        """Create notification for application status update"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            if not application_status or not application_status.strip():
                raise ValidationError("Application status is required")
            if not opportunity_title or not opportunity_title.strip():
                raise ValidationError("Opportunity title is required")
            
            valid_statuses = ["pending", "accepted", "rejected", "withdrawn"]
            if application_status not in valid_statuses:
                raise ValidationError(f"Invalid application status. Must be one of: {valid_statuses}")
            
            notification_data = NotificationCreate(
                user_id=user_id,
                type="application",
                title="Application Update",
                message=f"Your application for '{opportunity_title.strip()}' has been {application_status}",
                data={"status": application_status}
            )
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating application notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create application notification: {str(e)}")
    
    async def create_verification_notification(self, user_id: str, verification_status: str) -> Dict[str, Any]:
        """Create notification for verification status update"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            if not verification_status or not verification_status.strip():
                raise ValidationError("Verification status is required")
            
            valid_statuses = ["pending", "approved", "rejected"]
            if verification_status not in valid_statuses:
                raise ValidationError(f"Invalid verification status. Must be one of: {valid_statuses}")
            
            notification_data = NotificationCreate(
                user_id=user_id,
                type="verification",
                title="Verification Update",
                message=f"Your verification status has been updated to: {verification_status}",
                data={"status": verification_status}
            )
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating verification notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create verification notification: {str(e)}")
    
    async def create_moderation_notification(self, user_id: str, content_type: str, moderation_status: str) -> Dict[str, Any]:
        """Create notification for content moderation"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            if not content_type or not content_type.strip():
                raise ValidationError("Content type is required")
            if not moderation_status or not moderation_status.strip():
                raise ValidationError("Moderation status is required")
            
            valid_statuses = ["pending", "approved", "rejected"]
            if moderation_status not in valid_statuses:
                raise ValidationError(f"Invalid moderation status. Must be one of: {valid_statuses}")
            
            notification_data = NotificationCreate(
                user_id=user_id,
                type="moderation",
                title="Content Moderation",
                message=f"Your {content_type.strip()} has been {moderation_status}",
                data={"content_type": content_type, "status": moderation_status}
            )
            
            return await self.create_notification(notification_data)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating moderation notification for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create moderation notification: {str(e)}")
    
    async def cleanup_old_notifications(self, days_old: int = 30) -> int:
        """Clean up old notifications"""
        try:
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
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            # Don't fail the main operation due to rate limit check failure
            pass
    
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
                    
        except Exception as e:
            logger.error(f"Error cleaning up old notifications for user {user_id}: {e}")
            # Don't fail the main operation due to cleanup failure
            pass
    
    async def _batch_update_notifications(self, notification_ids: List[str], update_data: Dict[str, Any]) -> None:
        """Update multiple notifications in a batch"""
        try:
            for notification_id in notification_ids:
                await self.notification_service.update(notification_id, update_data)
        except Exception as e:
            logger.error(f"Error in batch update notifications: {e}")
            raise DatabaseError(f"Failed to batch update notifications: {str(e)}") 