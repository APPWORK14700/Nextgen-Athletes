"""
Media API endpoints for Athletes Networking App

This module provides endpoints for media upload, management, and AI analysis using the new media service structure.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.api.dependencies import get_current_user, require_athlete_role, require_scout_role
from app.services.media_service import MediaService
from app.models.media import MediaCreate, MediaUpdate
from app.models.media_responses import MediaResponse, MediaListResponse, MediaStatusResponse, BulkUploadResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)

# Initialize services
media_service = MediaService()

@router.post("/upload", response_model=MediaResponse)
async def upload_media(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    type: str = Form(...),
    current_user: dict = Depends(require_athlete_role)
):
    """Upload media file with metadata"""
    try:
        # Validate file type
        if type not in ["video", "image", "reel"]:
            raise ValidationError("Invalid media type. Must be 'video', 'image', or 'reel'")
        
        # For now, we'll use a placeholder URL since we need to implement actual file upload
        # In production, you'd upload to cloud storage and get the URL
        file_url = f"https://storage.example.com/{current_user['uid']}/{file.filename}"
        
        # Create media data using the new structure
        media_data = MediaCreate(
            type=type,
            description=description
        )
        
        # Upload using the new service
        result = await media_service.upload_media(
            athlete_id=current_user["uid"],
            media_data=media_data,
            file_url=file_url
        )
        
        logger.info(f"Media uploaded successfully: {result.id}")
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_media(
    files: List[UploadFile] = File(...),
    descriptions: Optional[str] = Form(None),  # Comma-separated descriptions
    types: Optional[str] = Form(None),  # Comma-separated types
    current_user: dict = Depends(require_athlete_role)
):
    """Bulk upload multiple media files"""
    try:
        if len(files) > 10:  # Limit to 10 files
            raise ValidationError("Maximum 10 files per bulk upload")
        
        # Parse descriptions and types
        desc_list = descriptions.split(",") if descriptions else [""] * len(files)
        type_list = types.split(",") if types else ["video"] * len(files)
        
        # Ensure we have enough descriptions and types
        while len(desc_list) < len(files):
            desc_list.append("")
        while len(type_list) < len(files):
            type_list.append("video")
        
        # Prepare media list for bulk upload
        media_list = []
        for i, file in enumerate(files):
            file_url = f"https://storage.example.com/{current_user['uid']}/{file.filename}"
            media_list.append({
                "metadata": {
                    "type": type_list[i],
                    "description": desc_list[i]
                },
                "file_url": file_url
            })
        
        result = await media_service.bulk_upload_media(
            athlete_id=current_user["uid"],
            media_list=media_list
        )
        
        logger.info(f"Bulk upload completed: {result.uploaded_count} successful, {result.failed_count} failed")
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=MediaListResponse)
async def get_my_media(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete_role)
):
    """Get media for current athlete"""
    try:
        result = await media_service.get_athlete_media(
            athlete_id=current_user["uid"],
            limit=limit,
            offset=offset
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting athlete media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}", response_model=MediaResponse)
async def get_media(
    media_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific media by ID"""
    try:
        media = await media_service.get_media_by_id(media_id)
        if not media:
            raise ResourceNotFoundError("Media not found")
        
        # Check permissions
        if current_user.get("role") == "athlete" and media.athlete_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to view this media")
        elif current_user.get("role") == "scout" and media.moderation_status != "approved":
            raise AuthorizationError("Media not available for viewing")
        
        return media
        
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=404 if isinstance(e, ResourceNotFoundError) else 403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_id: str,
    description: Optional[str] = Form(None),
    current_user: dict = Depends(require_athlete_role)
):
    """Update media metadata"""
    try:
        # Create update data
        update_data = MediaUpdate(description=description)
        
        # Update media
        result = await media_service.update_media(
            media_id=media_id,
            media_data=update_data,
            athlete_id=current_user["uid"]
        )
        
        logger.info(f"Media {media_id} updated successfully")
        return result
        
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{media_id}")
async def delete_media(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Delete media"""
    try:
        success = await media_service.delete_media(
            media_id=media_id,
            athlete_id=current_user["uid"]
        )
        
        if success:
            logger.info(f"Media {media_id} deleted successfully")
            return {"message": "Media deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete media")
        
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{media_id}/retry-analysis")
async def retry_ai_analysis(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Retry AI analysis for failed media"""
    try:
        success = await media_service.retry_ai_analysis(
            media_id=media_id,
            athlete_id=current_user["uid"]
        )
        
        if success:
            logger.info(f"AI analysis retry initiated for media {media_id}")
            return {"message": "AI analysis retry initiated"}
        else:
            raise HTTPException(status_code=400, detail="Failed to retry AI analysis")
        
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrying AI analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}/status", response_model=MediaStatusResponse)
async def get_media_status(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Get AI analysis status for media"""
    try:
        result = await media_service.get_media_status(
            media_id=media_id,
            athlete_id=current_user["uid"]
        )
        return result
        
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting media status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search", response_model=MediaListResponse)
async def search_media(
    query: str = Query(..., description="Search query"),
    media_type: Optional[str] = Query(None, description="Media type filter"),
    sport_category: Optional[str] = Query(None, description="Sport category filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Search media by various criteria"""
    try:
        result = await media_service.search_media(
            query=query,
            media_type=media_type,
            sport_category=sport_category,
            limit=limit,
            offset=offset
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/type/{media_type}", response_model=MediaListResponse)
async def get_media_by_type(
    media_type: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    moderation_status: str = Query("approved", description="Moderation status filter"),
    current_user: dict = Depends(get_current_user)
):
    """Get media by type with optional moderation status filter"""
    try:
        result = await media_service.get_media_by_type(
            media_type=media_type,
            limit=limit,
            offset=offset,
            moderation_status=moderation_status
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting media by type: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/recommendations/reels", response_model=List[MediaResponse])
async def get_recommended_reels(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scout_role)
):
    """Get recommended reels for scout"""
    try:
        result = await media_service.get_recommended_reels(
            scout_id=current_user["uid"],
            limit=limit
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recommended reels: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/recommendations/sport/{sport_category}", response_model=List[MediaResponse])
async def get_recommended_media_by_sport(
    sport_category: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scout_role)
):
    """Get recommended media by sport category"""
    try:
        result = await media_service.get_recommended_media_by_sport(
            sport_category=sport_category,
            limit=limit
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recommended media by sport: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/trending", response_model=List[MediaResponse])
async def get_trending_media(
    limit: int = Query(20, ge=1, le=100),
    time_window_hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    current_user: dict = Depends(get_current_user)
):
    """Get trending media based on recent activity"""
    try:
        result = await media_service.get_trending_media(
            limit=limit,
            time_window_hours=time_window_hours
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting trending media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/bulk")
async def bulk_delete_media(
    media_ids: List[str] = Query(..., description="List of media IDs to delete"),
    current_user: dict = Depends(require_athlete_role)
):
    """Bulk delete media files"""
    try:
        success = await media_service.bulk_delete_media(
            media_ids=media_ids,
            athlete_id=current_user["uid"]
        )
        
        if success:
            logger.info(f"Bulk delete completed for {len(media_ids)} media files")
            return {"message": f"Successfully deleted {len(media_ids)} media files"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete media")
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/rate-limit/info")
async def get_rate_limit_info(
    current_user: dict = Depends(require_athlete_role)
):
    """Get upload rate limit information for current athlete"""
    try:
        result = await media_service.get_upload_rate_limit_info(
            athlete_id=current_user["uid"]
        )
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting rate limit info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/service/status")
async def get_service_status():
    """Get media service status"""
    try:
        result = media_service.get_service_status()
        return result
        
    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 