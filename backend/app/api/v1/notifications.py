"""
Notifications API endpoints for Athletes Networking App

This module provides endpoints for notification management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Form, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.api.dependencies import get_current_user
from app.services.notification_service import NotificationService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

# Pydantic models
class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool
    created_at: str

class NotificationListResponse(BaseResponse):
    notifications: List[NotificationResponse]

class NotificationSettingsResponse(BaseModel):
    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    message_notifications: bool
    opportunity_notifications: bool
    application_notifications: bool

class NotificationPreferencesResponse(BaseModel):
    digest_frequency: str
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    categories: dict

# Initialize services
notification_service = NotificationService()

@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    type: Optional[str] = Query(None, description="Notification type filter"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get notifications for authenticated user"""
    try:
        filters = {"user_id": current_user["uid"]}
        
        if type:
            filters["type"] = type
        if unread_only:
            filters["is_read"] = False
        
        notifications = await notification_service.get_user_notifications(
            user_id=current_user["uid"],
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return NotificationListResponse(
            notifications=[NotificationResponse(**notif) for notif in notifications["notifications"]]
        )
        
    except Exception as e:
        logger.error(f"Error getting notifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific notification"""
    try:
        notification = await notification_service.get_notification_by_id(
            notification_id=notification_id,
            user_id=current_user["uid"]
        )
        return NotificationResponse(**notification)
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        logger.error(f"Error getting notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark notification as read"""
    try:
        await notification_service.mark_as_read(
            notification_id=notification_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Notification {notification_id} marked as read by user {current_user['uid']}")
        return {"message": "Notification marked as read"}
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# NEW MISSING ENDPOINTS - Individual notification read management

@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_single_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a specific notification as read (PUT version as per API specification)
    """
    try:
        notification = await notification_service.mark_notification_as_read(
            notification_id=notification_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Notification {notification_id} marked as read by user {current_user['uid']}")
        return NotificationResponse(**notification)
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/read-all")
async def mark_all_notifications_read_put(
    current_user: dict = Depends(get_current_user)
):
    """
    Mark all notifications as read (PUT version as per API specification)
    """
    try:
        count = await notification_service.mark_all_as_read(current_user["uid"])
        logger.info(f"All notifications marked as read by user {current_user['uid']}")
        return {"message": "All notifications marked as read", "count": count}
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/mark-all-read")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user)
):
    """Mark all notifications as read"""
    try:
        count = await notification_service.mark_all_as_read(current_user["uid"])
        logger.info(f"All notifications marked as read by user {current_user['uid']}")
        return {"message": "All notifications marked as read", "count": count}
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete notification"""
    try:
        await notification_service.delete_notification(
            notification_id=notification_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Notification {notification_id} deleted by user {current_user['uid']}")
        return {"message": "Notification deleted successfully"}
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/")
async def delete_all_notifications(
    current_user: dict = Depends(get_current_user)
):
    """Delete all notifications for user"""
    try:
        count = await notification_service.delete_all_notifications(current_user["uid"])
        logger.info(f"All notifications deleted by user {current_user['uid']}")
        return {"message": "All notifications deleted", "count": count}
        
    except Exception as e:
        logger.error(f"Error deleting all notifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/unread/count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get unread notification count"""
    try:
        count = await notification_service.get_unread_count(current_user["uid"])
        return {"unread_count": count}
        
    except Exception as e:
        logger.error(f"Error getting unread count: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/unread/count-by-type")
async def get_unread_count_by_type(
    current_user: dict = Depends(get_current_user)
):
    """Get unread notification count by type"""
    try:
        counts = await notification_service.get_unread_count_by_type(current_user["uid"])
        return {"unread_counts": counts}
        
    except Exception as e:
        logger.error(f"Error getting unread count by type: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: dict = Depends(get_current_user)
):
    """Get notification settings"""
    try:
        settings = await notification_service.get_user_settings(current_user["uid"])
        return NotificationSettingsResponse(**settings)
        
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    email_enabled: bool = Form(...),
    push_enabled: bool = Form(...),
    in_app_enabled: bool = Form(...),
    message_notifications: bool = Form(...),
    opportunity_notifications: bool = Form(...),
    application_notifications: bool = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Update notification settings"""
    try:
        settings_data = {
            "email_enabled": email_enabled,
            "push_enabled": push_enabled,
            "in_app_enabled": in_app_enabled,
            "message_notifications": message_notifications,
            "opportunity_notifications": opportunity_notifications,
            "application_notifications": application_notifications
        }
        
        settings = await notification_service.update_user_settings(
            user_id=current_user["uid"],
            settings=settings_data
        )
        logger.info(f"Notification settings updated by user {current_user['uid']}")
        return NotificationSettingsResponse(**settings)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating notification settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/settings/reset")
async def reset_notification_settings(
    current_user: dict = Depends(get_current_user)
):
    """Reset notification settings to defaults"""
    try:
        settings = await notification_service.reset_user_settings(current_user["uid"])
        logger.info(f"Notification settings reset by user {current_user['uid']}")
        return {"message": "Settings reset to defaults", "settings": settings}
        
    except Exception as e:
        logger.error(f"Error resetting notification settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test")
async def send_test_notification(
    type: str = Form(...),
    title: str = Form(...),
    message: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Send a test notification"""
    try:
        notification = await notification_service.create_notification(
            user_id=current_user["uid"],
            type=type,
            title=title,
            message=message,
            data={"test": True}
        )
        logger.info(f"Test notification sent to user {current_user['uid']}")
        return {"message": "Test notification sent", "notification": notification}
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user)
):
    """Get notification preferences"""
    try:
        preferences = await notification_service.get_user_preferences(current_user["uid"])
        return NotificationPreferencesResponse(**preferences)
        
    except Exception as e:
        logger.error(f"Error getting notification preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    digest_frequency: str = Form(...),
    quiet_hours_start: Optional[str] = Form(None),
    quiet_hours_end: Optional[str] = Form(None),
    categories: str = Form(..., description="JSON string of category preferences"),
    current_user: dict = Depends(get_current_user)
):
    """Update notification preferences"""
    try:
        import json
        
        preferences_data = {
            "digest_frequency": digest_frequency,
            "quiet_hours_start": quiet_hours_start,
            "quiet_hours_end": quiet_hours_end,
            "categories": json.loads(categories)
        }
        
        preferences = await notification_service.update_user_preferences(
            user_id=current_user["uid"],
            preferences=preferences_data
        )
        logger.info(f"Notification preferences updated by user {current_user['uid']}")
        return NotificationPreferencesResponse(**preferences)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating notification preferences: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/history")
async def get_notification_history(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    type: Optional[str] = Query(None, description="Notification type filter"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get notification history"""
    try:
        history = await notification_service.get_notification_history(
            user_id=current_user["uid"],
            days=days,
            type=type,
            page=(offset // limit) + 1,
            limit=limit
        )
        return history
        
    except Exception as e:
        logger.error(f"Error getting notification history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk/read")
async def mark_notifications_bulk_read(
    notification_ids: List[str] = Form(..., description="List of notification IDs"),
    current_user: dict = Depends(get_current_user)
):
    """Mark multiple notifications as read"""
    try:
        count = await notification_service.mark_notifications_bulk_read(
            user_id=current_user["uid"],
            notification_ids=notification_ids
        )
        logger.info(f"{count} notifications marked as read by user {current_user['uid']}")
        return {"message": f"{count} notifications marked as read"}
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking notifications bulk read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# NEW MISSING ENDPOINT - PUT /bulk-read as specified in API specification

@router.put("/bulk-read")
async def mark_notifications_bulk_read_put(
    notification_ids: List[str] = Form(..., description="List of notification IDs"),
    current_user: dict = Depends(get_current_user)
):
    """
    Marks multiple notifications as read (PUT method as per API spec)
    """
    try:
        result = await notification_service.mark_notifications_read(
            user_id=current_user["uid"],
            notification_ids=notification_ids
        )
        
        logger.info(f"Bulk read operation completed for {len(notification_ids)} notifications by user {current_user['uid']}")
        return {"message": "Notifications marked as read"}
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking notifications bulk read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/bulk")
async def delete_notifications_bulk(
    notification_ids: List[str] = Form(..., description="List of notification IDs"),
    current_user: dict = Depends(get_current_user)
):
    """Delete multiple notifications"""
    try:
        count = await notification_service.delete_notifications_bulk(
            user_id=current_user["uid"],
            notification_ids=notification_ids
        )
        logger.info(f"{count} notifications deleted by user {current_user['uid']}")
        return {"message": f"{count} notifications deleted successfully"}
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting notifications bulk: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 