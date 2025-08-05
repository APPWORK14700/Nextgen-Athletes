"""
Athletes API endpoints for Athletes Networking App

This module provides endpoints for athlete profile management and search.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, require_athlete, require_scout
from app.services.athlete_service import AthleteService
from app.services.media_service import MediaService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/athletes", tags=["athletes"])

# Pydantic models
class AthleteSearchResponse(BaseModel):
    count: int
    results: List[dict]

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

# Initialize services
athlete_service = AthleteService()
media_service = MediaService()

@router.get("/")
async def search_athletes(
    sport_category_id: Optional[str] = Query(None, description="Sport category ID"),
    position: Optional[str] = Query(None, description="Position filter"),
    min_age: Optional[int] = Query(None, ge=13, le=50, description="Minimum age"),
    max_age: Optional[int] = Query(None, ge=13, le=50, description="Maximum age"),
    gender: Optional[str] = Query(None, description="Gender filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    min_rating: Optional[str] = Query(None, description="Minimum AI rating"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    current_user: dict = Depends(require_scout)
):
    """
    Search for athletes based on filter criteria
    Only available to verified scouts
    """
    try:
        filters = {}
        
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        if position:
            filters["position"] = position
        if min_age:
            filters["min_age"] = min_age
        if max_age:
            filters["max_age"] = max_age
        if gender:
            filters["gender"] = gender
        if location:
            filters["location"] = location
        if min_rating:
            filters["min_rating"] = min_rating
        
        result = await athlete_service.search_athletes(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return {
            "count": result["total"],
            "results": result["athletes"]
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/{athlete_id}")
async def get_athlete_profile(
    athlete_id: str,
    current_user: dict = Depends(require_scout)
):
    """
    Retrieve a specific athlete's public profile
    Only available to verified scouts
    """
    try:
        profile = await athlete_service.get_profile_by_user_id(athlete_id)
        return profile
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Athlete not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get athlete profile: {str(e)}")

# NEW MISSING ENDPOINTS

@router.get("/me/media", response_model=List[MediaResponse])
async def get_my_media(
    type: Optional[str] = Query(None, description="Media type filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete)
):
    """
    Retrieve all media for the currently authenticated athlete
    """
    try:
        filters = {"user_id": current_user["uid"]}
        if type:
            if type not in ["video", "image", "reel"]:
                raise ValidationError("Invalid media type. Must be 'video', 'image', or 'reel'")
            filters["type"] = type
        
        media_list = await media_service.get_user_media(
            user_id=current_user["uid"],
            user_type="athlete",
            page=(offset // limit) + 1,
            limit=limit,
            filters=filters
        )
        
        return [MediaResponse(**media) for media in media_list]
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve media: {str(e)}")

@router.get("/{athlete_id}/media", response_model=List[MediaResponse])
async def get_athlete_media(
    athlete_id: str,
    type: Optional[str] = Query(None, description="Media type filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_scout)
):
    """
    Retrieve all media for a specific athlete
    Only available to verified scouts - shows only approved media
    """
    try:
        # Verify athlete exists
        await athlete_service.get_profile_by_user_id(athlete_id)
        
        filters = {
            "user_id": athlete_id,
            "moderation_status": "approved"  # Only show approved media to scouts
        }
        if type:
            if type not in ["video", "image", "reel"]:
                raise ValidationError("Invalid media type. Must be 'video', 'image', or 'reel'")
            filters["type"] = type
        
        media_list = await media_service.get_user_media(
            user_id=athlete_id,
            user_type="athlete",
            page=(offset // limit) + 1,
            limit=limit,
            filters=filters
        )
        
        return [MediaResponse(**media) for media in media_list]
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Athlete not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve athlete media: {str(e)}")

@router.get("/{athlete_id}/stats")
async def get_athlete_stats(
    athlete_id: str,
    sport_category_id: Optional[str] = Query(None, description="Sport category filter"),
    season: Optional[str] = Query(None, description="Season filter"),
    current_user: dict = Depends(require_scout)
):
    """
    Retrieve stats for a specific athlete
    Only available to verified scouts
    """
    try:
        # Verify athlete exists
        await athlete_service.get_profile_by_user_id(athlete_id)
        
        filters = {"athlete_id": athlete_id}
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        if season:
            filters["season"] = season
        
        stats = await athlete_service.get_stats(athlete_id, filters)
        return stats
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Athlete not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

@router.post("/me/profile")
async def create_athlete_profile(
    profile_data: dict,
    current_user: dict = Depends(require_athlete)
):
    """
    Create athlete profile
    Only available to users with athlete role
    """
    try:
        # Check if user already has athlete role
        if current_user.get("role") != "athlete":
            raise ValidationError("Only users with athlete role can create athlete profiles")
        
        result = await athlete_service.create_profile(current_user["uid"], profile_data)
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")

@router.get("/me/profile")
async def get_my_profile(
    current_user: dict = Depends(require_athlete)
):
    """
    Get authenticated athlete's profile
    """
    try:
        profile = await athlete_service.get_profile_by_user_id(current_user["uid"])
        return profile
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Profile not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")

@router.put("/me/profile")
async def update_my_profile(
    profile_data: dict,
    current_user: dict = Depends(require_athlete)
):
    """
    Update authenticated athlete's profile
    """
    try:
        result = await athlete_service.update_profile(current_user["uid"], profile_data)
        return result
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Profile not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")

@router.get("/me/stats")
async def get_my_stats(
    sport_category_id: Optional[str] = Query(None, description="Sport category filter"),
    season: Optional[str] = Query(None, description="Season filter"),
    current_user: dict = Depends(require_athlete)
):
    """
    Get authenticated athlete's stats
    """
    try:
        filters = {"athlete_id": current_user["uid"]}
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        if season:
            filters["season"] = season
            
        stats = await athlete_service.get_stats(current_user["uid"], filters)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {str(e)}")

@router.get("/me/analytics")
async def get_my_analytics(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(require_athlete)
):
    """
    Get analytics for authenticated athlete
    """
    try:
        analytics = await athlete_service.get_analytics(
            user_id=current_user["uid"],
            start_date=start_date,
            end_date=end_date
        )
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")

@router.get("/me/recommendations")
async def get_my_recommendations(
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete)
):
    """
    Get personalized recommendations for authenticated athlete
    """
    try:
        recommendations = await athlete_service.get_recommendations(
            user_id=current_user["uid"],
            sport=sport,
            limit=limit,
            offset=offset
        )
        return recommendations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve recommendations: {str(e)}")

@router.post("/me/verify")
async def submit_verification(
    document_type: str,
    document_url: str,
    additional_info: Optional[str] = None,
    current_user: dict = Depends(require_athlete)
):
    """
    Submit verification documents for athlete profile
    """
    try:
        verification_data = {
            "document_type": document_type,
            "document_url": document_url,
            "additional_info": additional_info
        }
        
        result = await athlete_service.submit_verification(current_user["uid"], verification_data)
        return {"message": "Verification submitted for review", "verification": result}
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit verification: {str(e)}")

@router.get("/me/verification/status")
async def get_verification_status(
    current_user: dict = Depends(require_athlete)
):
    """
    Check verification status of authenticated athlete
    """
    try:
        status = await athlete_service.get_verification_status(current_user["uid"])
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get verification status: {str(e)}")

@router.get("/me/verification/documents")
async def get_verification_documents(
    current_user: dict = Depends(require_athlete)
):
    """
    Get all verification documents submitted by athlete
    """
    try:
        documents = await athlete_service.get_verification_documents(current_user["uid"])
        return documents
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve verification documents: {str(e)}") 