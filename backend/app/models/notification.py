from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Notification(BaseModelWithID):
    """Notification model for user notifications"""
    user_id: str
    type: Literal["message", "opportunity", "application", "verification", "moderation"]
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    is_read: bool = False


class NotificationCreate(BaseModel):
    """Model for creating notification"""
    user_id: str
    type: Literal["message", "opportunity", "application", "verification", "moderation"]
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None


class NotificationUpdate(BaseModel):
    """Model for updating notification"""
    is_read: bool


class NotificationSearchFilters(BaseModel):
    """Model for notification search filters"""
    type: Optional[Literal["message", "opportunity", "application", "verification", "moderation"]] = None
    unread_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class NotificationBulkRead(BaseModel):
    """Model for bulk marking notifications as read"""
    notification_ids: list[str] 