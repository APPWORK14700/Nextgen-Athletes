from fastapi import APIRouter, Depends, HTTPException, Query, Form
from typing import List, Optional
import logging

from app.models.user import UserResponse, UserSearchFilters, UserSearchResponse
from app.models.verification import VerificationDocumentResponse, VerificationStatusUpdate
from app.models.report import UserReportResponse, ReportStatusUpdate
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.scout_service import ScoutService
from app.api.dependencies import get_current_user, require_admin_role
from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Service instances
auth_service = AuthService()
user_service = UserService()
scout_service = ScoutService()


@router.get("/users", response_model=UserSearchResponse)
async def search_users(
    query: Optional[str] = Query(None, description="Search query"),
    role: Optional[str] = Query(None, description="User role filter"),
    status: Optional[str] = Query(None, description="User status filter"),
    verified: Optional[bool] = Query(None, description="Verification status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_admin_role)
):
    """Search users (admin only)"""
    try:
        filters = UserSearchFilters(
            query=query,
            role=role,
            status=status,
            verified=verified
        )
        
        result = await user_service.search_users_admin(
            filters=filters,
            page=page,
            limit=limit
        )
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_admin(
    user_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """Get user details (admin only)"""
    try:
        user = await user_service.get_user_by_id_admin(user_id)
        if not user:
            raise ResourceNotFoundError("User not found")
        return user
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status: str = Form(..., description="New user status"),
    reason: Optional[str] = Form(None, description="Reason for status change"),
    current_user: dict = Depends(require_admin_role)
):
    """Update user status (admin only)"""
    try:
        result = await user_service.update_user_status_admin(
            user_id=user_id,
            status=status,
            reason=reason,
            admin_id=current_user["uid"]
        )
        logger.info(f"User {user_id} status updated to {status} by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: str,
    reason: Optional[str] = Form(None, description="Reason for deletion"),
    current_user: dict = Depends(require_admin_role)
):
    """Delete user (admin only)"""
    try:
        await user_service.delete_user_admin(
            user_id=user_id,
            reason=reason,
            admin_id=current_user["uid"]
        )
        logger.info(f"User {user_id} deleted by admin {current_user['uid']}")
        return {"message": "User deleted successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting user admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Verification Management
@router.get("/verifications", response_model=List[VerificationDocumentResponse])
async def get_pending_verifications(
    status: Optional[str] = Query("pending", description="Verification status"),
    user_type: Optional[str] = Query(None, description="User type filter"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_admin_role)
):
    """Get pending verifications (admin only)"""
    try:
        verifications = await scout_service.get_verifications_admin(
            status=status,
            user_type=user_type,
            page=page,
            limit=limit
        )
        return verifications
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting pending verifications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/verifications/{verification_id}", response_model=VerificationDocumentResponse)
async def get_verification_admin(
    verification_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """Get verification details (admin only)"""
    try:
        verification = await scout_service.get_verification_admin(verification_id)
        if not verification:
            raise ResourceNotFoundError("Verification not found")
        return verification
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting verification admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/verifications/{verification_id}/status")
async def update_verification_status(
    verification_id: str,
    status_update: VerificationStatusUpdate,
    current_user: dict = Depends(require_admin_role)
):
    """Update verification status (admin only)"""
    try:
        result = await scout_service.update_verification_status_admin(
            verification_id=verification_id,
            status=status_update.status,
            notes=status_update.notes,
            admin_id=current_user["uid"]
        )
        logger.info(f"Verification {verification_id} status updated to {status_update.status} by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating verification status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Report Management
@router.get("/reports", response_model=List[UserReportResponse])
async def get_user_reports(
    status: Optional[str] = Query("pending", description="Report status"),
    report_type: Optional[str] = Query(None, description="Report type filter"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_admin_role)
):
    """Get user reports (admin only)"""
    try:
        reports = await user_service.get_user_reports_admin(
            status=status,
            report_type=report_type,
            page=page,
            limit=limit
        )
        return reports
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user reports: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/{report_id}", response_model=UserReportResponse)
async def get_user_report_admin(
    report_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """Get user report details (admin only)"""
    try:
        report = await user_service.get_user_report_admin(report_id)
        if not report:
            raise ResourceNotFoundError("Report not found")
        return report
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user report admin: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/reports/{report_id}/status")
async def update_report_status(
    report_id: str,
    status_update: ReportStatusUpdate,
    current_user: dict = Depends(require_admin_role)
):
    """Update report status (admin only)"""
    try:
        result = await user_service.update_report_status_admin(
            report_id=report_id,
            status=status_update.status,
            resolution=status_update.resolution,
            admin_id=current_user["uid"]
        )
        logger.info(f"Report {report_id} status updated to {status_update.status} by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating report status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Analytics and Statistics
@router.get("/stats/overview")
async def get_admin_stats_overview(
    current_user: dict = Depends(require_admin_role)
):
    """Get admin dashboard statistics"""
    try:
        stats = await user_service.get_admin_stats_overview()
        return stats
    except Exception as e:
        logger.error(f"Error getting admin stats overview: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/users")
async def get_user_stats(
    period: str = Query("month", description="Time period (day/week/month/year)"),
    current_user: dict = Depends(require_admin_role)
):
    """Get user statistics"""
    try:
        stats = await user_service.get_user_stats_admin(period)
        return stats
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/verifications")
async def get_verification_stats(
    period: str = Query("month", description="Time period (day/week/month/year)"),
    current_user: dict = Depends(require_admin_role)
):
    """Get verification statistics"""
    try:
        stats = await scout_service.get_verification_stats_admin(period)
        return stats
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting verification stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/reports")
async def get_report_stats(
    period: str = Query("month", description="Time period (day/week/month/year)"),
    current_user: dict = Depends(require_admin_role)
):
    """Get report statistics"""
    try:
        stats = await user_service.get_report_stats_admin(period)
        return stats
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting report stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# System Management
@router.get("/system/health")
async def get_system_health(
    current_user: dict = Depends(require_admin_role)
):
    """Get system health status"""
    try:
        health = await user_service.get_system_health()
        return health
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/system/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, description="Log level filter"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=200, description="Items per page"),
    current_user: dict = Depends(require_admin_role)
):
    """Get system logs (admin only)"""
    try:
        logs = await user_service.get_system_logs_admin(
            level=level,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        return logs
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting system logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/system/maintenance")
async def trigger_maintenance(
    maintenance_type: str = Form(..., description="Type of maintenance"),
    current_user: dict = Depends(require_admin_role)
):
    """Trigger system maintenance (admin only)"""
    try:
        result = await user_service.trigger_maintenance_admin(
            maintenance_type=maintenance_type,
            admin_id=current_user["uid"]
        )
        logger.info(f"Maintenance {maintenance_type} triggered by admin {current_user['uid']}")
        return result
    except (ValidationError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error triggering maintenance: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Content Moderation
@router.get("/moderation/flagged-content")
async def get_flagged_content(
    content_type: Optional[str] = Query(None, description="Content type filter"),
    status: Optional[str] = Query("pending", description="Moderation status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_admin_role)
):
    """Get flagged content for moderation"""
    try:
        content = await user_service.get_flagged_content_admin(
            content_type=content_type,
            status=status,
            page=page,
            limit=limit
        )
        return content
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting flagged content: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/moderation/{content_id}/status")
async def update_content_moderation_status(
    content_id: str,
    status: str = Form(..., description="New moderation status"),
    action: str = Form(..., description="Action taken (approve/reject/remove)"),
    reason: Optional[str] = Form(None, description="Reason for action"),
    current_user: dict = Depends(require_admin_role)
):
    """Update content moderation status"""
    try:
        result = await user_service.update_content_moderation_status_admin(
            content_id=content_id,
            status=status,
            action=action,
            reason=reason,
            admin_id=current_user["uid"]
        )
        logger.info(f"Content {content_id} moderation status updated to {status} by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating content moderation status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Bulk Operations
@router.post("/bulk/user-actions")
async def bulk_user_actions(
    user_ids: List[str] = Form(..., description="List of user IDs"),
    action: str = Form(..., description="Action to perform"),
    reason: Optional[str] = Form(None, description="Reason for action"),
    current_user: dict = Depends(require_admin_role)
):
    """Perform bulk actions on users"""
    try:
        result = await user_service.bulk_user_actions_admin(
            user_ids=user_ids,
            action=action,
            reason=reason,
            admin_id=current_user["uid"]
        )
        logger.info(f"Bulk action {action} performed on {len(user_ids)} users by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error performing bulk user actions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bulk/verification-actions")
async def bulk_verification_actions(
    verification_ids: List[str] = Form(..., description="List of verification IDs"),
    action: str = Form(..., description="Action to perform"),
    notes: Optional[str] = Form(None, description="Notes for action"),
    current_user: dict = Depends(require_admin_role)
):
    """Perform bulk actions on verifications"""
    try:
        result = await scout_service.bulk_verification_actions_admin(
            verification_ids=verification_ids,
            action=action,
            notes=notes,
            admin_id=current_user["uid"]
        )
        logger.info(f"Bulk action {action} performed on {len(verification_ids)} verifications by admin {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error performing bulk verification actions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 

@router.get("/content/pending")
async def get_pending_content(
    type: Optional[str] = Query(None, description="Content type filter"),
    moderation_status: Optional[str] = Query(None, description="Moderation status filter"),
    priority: Optional[str] = Query(None, description="Priority filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin_role)
):
    """
    Retrieve content pending moderation (both flagged content and content marked for review)
    """
    try:
        filters = {}
        if type:
            filters["type"] = type
        if moderation_status:
            filters["moderation_status"] = moderation_status
        if priority:
            filters["priority"] = priority
        
        # Get both flagged content and content requiring review
        pending_content = await user_service.get_pending_moderation_content(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return pending_content
        
    except Exception as e:
        logger.error(f"Error getting pending content: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/content/{content_id}/moderate")
async def moderate_content(
    content_id: str,
    action: str = Form(..., description="approve, reject, dismiss_flag, escalate, take_action"),
    reason: Optional[str] = Form(None),
    flag_id: Optional[str] = Form(None, description="Specific flag ID for flag-specific actions"),
    notes: Optional[str] = Form(None),
    current_user: dict = Depends(require_admin_role)
):
    """
    Unified moderation endpoint for handling content approval, rejection, and flag resolution
    """
    try:
        if action not in ["approve", "reject", "dismiss_flag", "escalate", "take_action"]:
            raise ValidationError("Invalid action. Must be one of: approve, reject, dismiss_flag, escalate, take_action")
        
        moderation_data = {
            "action": action,
            "reason": reason,
            "flag_id": flag_id,
            "notes": notes,
            "admin_id": current_user["uid"]
        }
        
        result = await user_service.moderate_content(
            content_id=content_id,
            moderation_data=moderation_data
        )
        
        logger.info(f"Content {content_id} moderated with action {action} by admin {current_user['uid']}")
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Content not found")
    except Exception as e:
        logger.error(f"Error moderating content: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 