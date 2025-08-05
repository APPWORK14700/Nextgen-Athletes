"""
Media API endpoints for Athletes Networking App

This module provides endpoints for media upload, management, and AI analysis.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.api.dependencies import get_current_user, require_athlete_role, require_scout_role
from app.services.media_service import MediaService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/media", tags=["media"])
logger = logging.getLogger(__name__)

# Pydantic models
class MediaResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    type: str
    ai_analysis: Optional[dict] = None
    created_at: str

class MediaSearchResponse(BaseResponse):
    media: List[MediaResponse]
    total: int

class MediaAnalysisResponse(BaseModel):
    media_id: str
    status: str
    rating: Optional[str] = None
    summary: Optional[str] = None
    detailed_analysis: Optional[dict] = None
    confidence_score: Optional[float] = None

# Initialize services
media_service = MediaService()

@router.post("/upload", response_model=MediaResponse)
async def upload_media(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    type: str = Form(...),
    sport: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: dict = Depends(require_athlete_role)
):
    """Upload media file with metadata"""
    try:
        # Validate file type and size
        if type not in ["video", "image", "reel"]:
            raise ValidationError("Invalid media type. Must be 'video', 'image', or 'reel'")
        
        # Parse tags if provided
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Upload media
        media_data = {
            "title": title,
            "description": description,
            "type": type,
            "sport": sport,
            "tags": tag_list
        }
        
        result = await media_service.upload_media(
            user_id=current_user["uid"],
            user_type="athlete",
            file=file,
            metadata=media_data
        )
        
        logger.info(f"Media uploaded successfully: {result['id']}")
        return MediaResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[MediaResponse])
async def get_user_media(
    user_type: Optional[str] = Query("athlete", description="User type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get media for current user"""
    try:
        media_list = await media_service.get_user_media(
            user_id=current_user["uid"],
            user_type=user_type,
            page=(offset // limit) + 1,
            limit=limit
        )
        return [MediaResponse(**media) for media in media_list]
    except Exception as e:
        logger.error(f"Error getting user media: {str(e)}")
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
        user_type = "athlete" if current_user.get("role") == "athlete" else "scout"
        
        # Athletes can only see their own media, scouts can see approved media
        if user_type == "athlete" and media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to view this media")
        elif user_type == "scout" and media.get("moderation_status") != "approved":
            raise AuthorizationError("Media not available for viewing")
        
        return MediaResponse(**media)
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=404 if isinstance(e, ResourceNotFoundError) else 403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[str] = None,
    current_user: dict = Depends(require_athlete_role)
):
    """Update media metadata"""
    try:
        # Verify ownership
        media = await media_service.get_media_by_id(media_id)
        if not media or media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to update this media")
        
        # Parse tags if provided
        tag_list = None
        if tags is not None:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Update media
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if tag_list is not None:
            update_data["tags"] = tag_list
        
        result = await media_service.update_media(media_id, update_data)
        return MediaResponse(**result)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{media_id}", status_code=204)
async def delete_media(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Delete media"""
    try:
        # Verify ownership
        media = await media_service.get_media_by_id(media_id)
        if not media or media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to delete this media")
        
        await media_service.delete_media(media_id)
        logger.info(f"Media deleted: {media_id}")
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search", response_model=MediaSearchResponse)
async def search_media(
    query: Optional[str] = Query(None, description="Search query"),
    sport: Optional[str] = Query(None, description="Sport filter"),
    type: Optional[str] = Query(None, description="Media type filter"),
    rating: Optional[str] = Query(None, description="AI rating filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Search media with filters"""
    try:
        user_type = "athlete" if current_user.get("role") == "athlete" else "scout"
        
        filters = {}
        if query:
            filters["query"] = query
        if sport:
            filters["sport"] = sport
        if type:
            if type not in ["video", "image", "reel"]:
                raise ValidationError("Invalid media type")
            filters["type"] = type
        if rating:
            filters["min_rating"] = rating
        
        # Only show approved media to scouts
        if user_type == "scout":
            filters["moderation_status"] = "approved"
        
        result = await media_service.search_media(
            filters=filters,
            user_id=current_user["uid"],
            user_type=user_type,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return MediaSearchResponse(
            media=[MediaResponse(**media) for media in result["media"]],
            total=result["total"]
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}/analysis", response_model=MediaAnalysisResponse)
async def get_media_analysis(
    media_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get AI analysis for media"""
    try:
        # Verify access to media
        media = await media_service.get_media_by_id(media_id)
        if not media:
            raise ResourceNotFoundError("Media not found")
        
        user_type = "athlete" if current_user.get("role") == "athlete" else "scout"
        
        # Check permissions
        if user_type == "athlete" and media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to view this analysis")
        elif user_type == "scout" and media.get("moderation_status") != "approved":
            raise AuthorizationError("Media not available for viewing")
        
        analysis = await media_service.get_media_analysis(media_id)
        return MediaAnalysisResponse(media_id=media_id, **analysis)
        
    except (ResourceNotFoundError, AuthorizationError) as e:
        status_code = 404 if isinstance(e, ResourceNotFoundError) else 403
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting media analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{media_id}/analyze")
async def trigger_media_analysis(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Trigger AI analysis for media"""
    try:
        # Verify media ownership
        media = await media_service.get_media_by_id(media_id)
        if not media or media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to analyze this media")
        
        # Trigger analysis
        await media_service.trigger_analysis(media_id)
        logger.info(f"Media analysis triggered for {media_id}")
        return {"message": "Media analysis triggered successfully"}
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error triggering media analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# New endpoints added according to API specification

@router.get("/reels/recommended", response_model=List[MediaResponse])
async def get_recommended_reels(
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(require_scout_role)
):
    """Get recommended reels feed for scouts based on AI ratings and scout preferences"""
    try:
        recommendations = await media_service.get_recommended_reels(
            scout_id=current_user["uid"],
            sport=sport,
            limit=limit
        )
        return [MediaResponse(**media) for media in recommendations]
        
    except Exception as e:
        logger.error(f"Error getting recommended reels: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}/status", response_model=MediaAnalysisResponse)
async def get_media_analysis_status(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Check AI analysis status for media (athlete owner only)"""
    try:
        # Verify media ownership
        media = await media_service.get_media_by_id(media_id)
        if not media or media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to view this media status")
        
        analysis_status = await media_service.get_analysis_status(media_id)
        return MediaAnalysisResponse(media_id=media_id, **analysis_status)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Media not found")
    except Exception as e:
        logger.error(f"Error getting media analysis status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{media_id}/retry-analysis")
async def retry_media_analysis(
    media_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Retry failed AI analysis for media (athlete owner only)"""
    try:
        # Verify media ownership
        media = await media_service.get_media_by_id(media_id)
        if not media or media.user_id != current_user["uid"]:
            raise AuthorizationError("Not authorized to retry analysis for this media")
        
        # Check if analysis can be retried
        analysis_status = await media_service.get_analysis_status(media_id)
        if analysis_status.get("status") not in ["failed", "error"]:
            raise ValidationError("Analysis can only be retried for failed analyses")
        
        await media_service.retry_analysis(media_id)
        logger.info(f"Media analysis retry initiated for {media_id}")
        return {"message": "AI analysis retry initiated"}
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrying media analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk-upload", response_model=List[MediaResponse])
async def bulk_upload_media(
    files: List[UploadFile] = File(...),
    metadata: str = Form(..., description="JSON string with metadata for each file"),
    current_user: dict = Depends(require_athlete_role)
):
    """Upload multiple media files in a single request"""
    try:
        import json
        
        # Parse metadata
        try:
            metadata_list = json.loads(metadata)
        except json.JSONDecodeError:
            raise ValidationError("Invalid metadata JSON format")
        
        if len(files) != len(metadata_list):
            raise ValidationError("Number of files must match number of metadata entries")
        
        if len(files) > 10:  # Reasonable limit for bulk upload
            raise ValidationError("Maximum 10 files can be uploaded at once")
        
        # Upload all files
        results = []
        for file, meta in zip(files, metadata_list):
            # Validate individual metadata
            if "type" not in meta or meta["type"] not in ["video", "image", "reel"]:
                raise ValidationError(f"Invalid or missing type for file {file.filename}")
            
            result = await media_service.upload_media(
                user_id=current_user["uid"],
                user_type="athlete",
                file=file,
                metadata=meta
            )
            results.append(MediaResponse(**result))
        
        logger.info(f"Bulk upload completed: {len(results)} files uploaded")
        return results
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/bulk-delete")
async def bulk_delete_media(
    media_ids: List[str],
    current_user: dict = Depends(require_athlete_role)
):
    """Delete multiple media files"""
    try:
        if len(media_ids) > 50:  # Reasonable limit
            raise ValidationError("Maximum 50 files can be deleted at once")
        
        # Verify ownership of all media files
        for media_id in media_ids:
            media = await media_service.get_media_by_id(media_id)
            if not media or media.user_id != current_user["uid"]:
                raise AuthorizationError(f"Not authorized to delete media {media_id}")
        
        # Delete all files
        deleted_count = 0
        for media_id in media_ids:
            try:
                await media_service.delete_media(media_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete media {media_id}: {str(e)}")
        
        logger.info(f"Bulk delete completed: {deleted_count}/{len(media_ids)} files deleted")
        return {"message": "Media files deleted successfully", "deleted_count": deleted_count}
        
    except (ValidationError, AuthorizationError) as e:
        raise HTTPException(status_code=400 if isinstance(e, ValidationError) else 403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk delete: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/recommended", response_model=List[MediaResponse])
async def get_recommended_media(
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    current_user: dict = Depends(get_current_user)
):
    """Get recommended media for current user"""
    try:
        user_type = "athlete" if current_user.get("role") == "athlete" else "scout"
        
        recommendations = await media_service.get_recommended_media(
            user_id=current_user["uid"],
            user_type=user_type,
            sport=sport,
            limit=limit
        )
        return [MediaResponse(**media) for media in recommendations]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting recommended media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/trending", response_model=List[MediaResponse])
async def get_trending_media(
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(10, ge=1, le=50, description="Number of trending media"),
    current_user: dict = Depends(get_current_user)
):
    """Get trending media"""
    try:
        trending = await media_service.get_trending_media(
            sport=sport,
            limit=limit
        )
        return [MediaResponse(**media) for media in trending]
    except Exception as e:
        logger.error(f"Error getting trending media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{media_id}/like")
async def like_media(
    media_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Like a media"""
    try:
        result = await media_service.like_media(media_id, current_user["uid"])
        return {"message": "Media liked successfully", "like_id": result["id"]}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error liking media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}/likes")
async def get_media_likes(
    media_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get likes for a media"""
    try:
        likes = await media_service.get_media_likes(
            media_id=media_id,
            page=(offset // limit) + 1,
            limit=limit
        )
        return {"likes": likes["likes"], "total": likes["total"]}
    except Exception as e:
        logger.error(f"Error getting media likes: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{media_id}/comment")
async def comment_on_media(
    media_id: str,
    content: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Add a comment to media"""
    try:
        comment = await media_service.add_comment(
            media_id=media_id,
            user_id=current_user["uid"],
            content=content
        )
        return {"message": "Comment added successfully", "comment": comment}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding comment: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{media_id}/comments")
async def get_media_comments(
    media_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get comments for a media"""
    try:
        comments = await media_service.get_media_comments(
            media_id=media_id,
            page=(offset // limit) + 1,
            limit=limit
        )
        return {"comments": comments["comments"], "total": comments["total"]}
    except Exception as e:
        logger.error(f"Error getting media comments: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{media_id}/comments/{comment_id}")
async def delete_media_comment(
    media_id: str,
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a comment (owner or commenter only)"""
    try:
        await media_service.delete_comment(
            comment_id=comment_id,
            user_id=current_user["uid"]
        )
        return {"message": "Comment deleted successfully"}
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting comment: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 