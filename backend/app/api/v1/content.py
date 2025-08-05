"""
Content API endpoints for Athletes Networking App

This module provides endpoints for content flagging and moderation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.api.dependencies import get_current_user, require_admin_role
from app.services.content_service import ContentService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/content", tags=["content"])

# Pydantic models for requests and responses
class FlagRequest(BaseModel):
    reason: str = Field(..., regex="^(inappropriate_content|fake_profile|spam|harassment|copyright|other)$")
    description: Optional[str] = Field(None, max_length=1000)
    evidence_url: Optional[HttpUrl] = None

class FlagResponse(BaseModel):
    id: str
    content_id: str
    content_type: str
    reporter_id: str
    reason: str
    description: Optional[str] = None
    evidence_url: Optional[str] = None
    status: str
    created_at: str
    resolved_at: Optional[str] = None

class FlagListResponse(BaseResponse):
    flags: List[FlagResponse]
    total: int
    page: int
    limit: int

# Initialize services
content_service = ContentService()

@router.post("/{content_id}/flag")
async def flag_content(
    content_id: str,
    content_type: str,  # Should be passed as query parameter
    request: FlagRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Flag content for review by administrators
    Available to all authenticated users
    """
    try:
        # Validate content type
        valid_types = ["media", "opportunity", "profile", "message"]
        if content_type not in valid_types:
            raise ValidationError(f"Invalid content type. Must be one of: {', '.join(valid_types)}")
        
        # Verify content exists
        await content_service.verify_content_exists(content_id, content_type)
        
        # Check if user has already flagged this content
        existing_flag = await content_service.get_user_flag_for_content(
            content_id=content_id,
            content_type=content_type,
            reporter_id=current_user["uid"]
        )
        
        if existing_flag:
            raise ValidationError("You have already flagged this content")
        
        # Create flag
        flag_data = {
            "content_id": content_id,
            "content_type": content_type,
            "reporter_id": current_user["uid"],
            **request.dict()
        }
        
        result = await content_service.create_flag(flag_data)
        
        return {"message": "Content flagged for review", "flag_id": result["id"]}
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flag content: {str(e)}"
        )

@router.get("/{content_id}/flags", response_model=FlagListResponse)
async def get_content_flags(
    content_id: str,
    content_type: str,  # Should be passed as query parameter
    current_user: dict = Depends(require_admin_role)
):
    """
    Retrieve all flags for a specific content item
    Only available to administrators
    """
    try:
        # Validate content type
        valid_types = ["media", "opportunity", "profile", "message"]
        if content_type not in valid_types:
            raise ValidationError(f"Invalid content type. Must be one of: {', '.join(valid_types)}")
        
        # Verify content exists
        await content_service.verify_content_exists(content_id, content_type)
        
        # Get all flags for the content
        result = await content_service.get_content_flags(content_id, content_type)
        
        return FlagListResponse(
            flags=[FlagResponse(**flag) for flag in result["flags"]],
            total=result["total"],
            page=1,
            limit=len(result["flags"])
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve content flags: {str(e)}"
        )

@router.get("/flags/my")
async def get_my_flags(
    status: Optional[str] = None,
    content_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Get flags submitted by the current user
    Available to all authenticated users
    """
    try:
        filters = {"reporter_id": current_user["uid"]}
        
        if status:
            if status not in ["pending", "resolved", "dismissed"]:
                raise ValidationError("Invalid status. Must be one of: pending, resolved, dismissed")
            filters["status"] = status
        
        if content_type:
            valid_types = ["media", "opportunity", "profile", "message"]
            if content_type not in valid_types:
                raise ValidationError(f"Invalid content type. Must be one of: {', '.join(valid_types)}")
            filters["content_type"] = content_type
        
        result = await content_service.get_user_flags(current_user["uid"], filters)
        
        return FlagListResponse(
            flags=[FlagResponse(**flag) for flag in result["flags"]],
            total=result["total"],
            page=1,
            limit=len(result["flags"])
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve flags: {str(e)}"
        )

@router.delete("/{content_id}/flags/{flag_id}")
async def remove_flag(
    content_id: str,
    flag_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a flag (only the reporter can remove their own flag if it's still pending)
    """
    try:
        # Verify flag ownership and status
        flag = await content_service.get_flag_by_id(flag_id)
        
        if flag["reporter_id"] != current_user["uid"]:
            raise AuthorizationError("You can only remove your own flags")
        
        if flag["status"] != "pending":
            raise ValidationError("Can only remove pending flags")
        
        if flag["content_id"] != content_id:
            raise ValidationError("Flag does not belong to this content")
        
        # Remove flag
        await content_service.remove_flag(flag_id)
        
        return {"message": "Flag removed successfully"}
        
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove flag: {str(e)}"
        )

@router.get("/flagged/summary")
async def get_flagged_content_summary(
    current_user: dict = Depends(require_admin_role)
):
    """
    Get summary of flagged content for admin dashboard
    Only available to administrators
    """
    try:
        result = await content_service.get_flagged_content_summary()
        
        return {
            "total_pending_flags": result["total_pending"],
            "flags_by_type": result["flags_by_type"],
            "flags_by_reason": result["flags_by_reason"],
            "recent_flags": result["recent_flags"],
            "high_priority_content": result["high_priority_content"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve flagged content summary: {str(e)}"
        ) 