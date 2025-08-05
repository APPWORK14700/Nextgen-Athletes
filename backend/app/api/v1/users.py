from fastapi import APIRouter, Depends, HTTPException, status, Query, Form
from typing import Optional

from ...models.user import User, UserUpdate, UserSettings
from ...models.base import SuccessResponse
from ...services.user_service import UserService
from ...api.dependencies import get_current_user, require_athlete_or_scout
from ...api.exceptions import ValidationException, NotFoundException, UserNotFoundError, InvalidUserDataError

router = APIRouter()


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    try:
        user_service = UserService()
        user_data = await user_service.get_user_by_id(current_user.id)
        
        if not user_data:
            raise NotFoundException("User", current_user.id)
        
        return user_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@router.put("/me")
async def update_current_user_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update current user profile"""
    try:
        user_service = UserService()
        updated_user = await user_service.update_user_profile(current_user.id, profile_data)
        return updated_user
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user profile"
        )


@router.delete("/me")
async def delete_current_user(current_user: User = Depends(get_current_user)):
    """Delete current user account"""
    try:
        user_service = UserService()
        await user_service.delete_user_account(current_user.id)
        return SuccessResponse(message="Account deleted successfully")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )


@router.get("/me/settings")
async def get_user_settings(current_user: User = Depends(get_current_user)):
    """Get user settings"""
    try:
        user_service = UserService()
        settings = await user_service.get_user_settings(current_user.id)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user settings"
        )


@router.put("/me/settings")
async def update_user_settings(
    settings: UserSettings,
    current_user: User = Depends(get_current_user)
):
    """Update user settings"""
    try:
        user_service = UserService()
        updated_user = await user_service.update_user_settings(current_user.id, settings)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user settings"
        )


@router.get("/me/analytics")
async def get_user_analytics(current_user: User = Depends(get_current_user)):
    """Get user analytics"""
    try:
        user_service = UserService()
        analytics = await user_service.get_user_analytics(current_user.id)
        return analytics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user analytics"
        )


@router.get("/me/blocked")
async def get_blocked_users(current_user: User = Depends(get_current_user)):
    """Get list of blocked users"""
    try:
        user_service = UserService()
        blocked_users = await user_service.get_blocked_users(current_user.id)
        return {"blocked_users": blocked_users}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get blocked users"
        )


@router.post("/{user_id}/block")
async def block_user(
    user_id: str,
    reason: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Block a user"""
    try:
        user_service = UserService()
        result = await user_service.block_user(current_user.id, user_id, reason)
        return SuccessResponse(message=result["message"])
    except (UserNotFoundError, InvalidUserDataError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to block user"
        )


@router.delete("/me/blocked/{blocked_user_id}")
async def unblock_user(
    blocked_user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Unblock a user"""
    try:
        user_service = UserService()
        result = await user_service.unblock_user(current_user.id, blocked_user_id)
        return SuccessResponse(message=result["message"])
    except (UserNotFoundError, InvalidUserDataError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unblock user"
        )


@router.post("/{user_id}/report")
async def report_user(
    user_id: str,
    reason: str = Form(...),
    description: Optional[str] = Form(None),
    evidence_url: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Report a user"""
    try:
        user_service = UserService()
        report_data = {
            "reason": reason,
            "description": description,
            "evidence_url": evidence_url
        }
        result = await user_service.report_user(current_user.id, user_id, report_data)
        return SuccessResponse(message=result["message"])
    except (UserNotFoundError, InvalidUserDataError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to report user"
        ) 