from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
import logging

from app.models.scout import (
    ScoutProfileCreate, ScoutProfileUpdate, ScoutProfileResponse,
    ScoutSearchFilters, ScoutSearchResponse, ScoutStatsResponse
)
from app.models.opportunity import (
    OpportunityCreate, OpportunityUpdate, OpportunityResponse,
    OpportunitySearchFilters, OpportunitySearchResponse
)
from app.models.media import MediaCreate, MediaResponse
from app.models.verification import VerificationDocumentCreate, VerificationDocumentResponse
from app.services.scout_service import ScoutService
from app.services.opportunity_service import OpportunityService
from app.services.media_service import MediaService
from app.services.auth_service import AuthService
from app.api.dependencies import get_current_user, require_scout_role, require_verified_scout
from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scouts", tags=["scouts"])

# Service instances
scout_service = ScoutService()
opportunity_service = OpportunityService()
media_service = MediaService()
auth_service = AuthService()


@router.post("/profile", response_model=ScoutProfileResponse)
async def create_scout_profile(
    profile: ScoutProfileCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new scout profile"""
    try:
        if current_user.get("role") != "scout":
            raise AuthorizationError("Only users with scout role can create scout profiles")
        
        result = await scout_service.create_profile(
            user_id=current_user["uid"],
            profile_data=profile
        )
        logger.info(f"Scout profile created for user {current_user['uid']}")
        return result
    except (ValidationError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating scout profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile", response_model=ScoutProfileResponse)
async def get_scout_profile(
    current_user: dict = Depends(require_scout_role)
):
    """Get current scout's profile"""
    try:
        profile = await scout_service.get_profile_by_user_id(current_user["uid"])
        if not profile:
            raise ResourceNotFoundError("Scout profile not found")
        return profile
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile/{scout_id}", response_model=ScoutProfileResponse)
async def get_scout_profile_by_id(
    scout_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get scout profile by ID"""
    try:
        profile = await scout_service.get_profile_by_id(scout_id)
        if not profile:
            raise ResourceNotFoundError("Scout profile not found")
        return profile
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout profile by ID: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/profile", response_model=ScoutProfileResponse)
async def update_scout_profile(
    profile: ScoutProfileUpdate,
    current_user: dict = Depends(require_scout_role)
):
    """Update current scout's profile"""
    try:
        result = await scout_service.update_profile(
            user_id=current_user["uid"],
            profile_data=profile
        )
        logger.info(f"Scout profile updated for user {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating scout profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/profile")
async def delete_scout_profile(
    current_user: dict = Depends(require_scout_role)
):
    """Delete current scout's profile"""
    try:
        await scout_service.delete_profile(current_user["uid"])
        logger.info(f"Scout profile deleted for user {current_user['uid']}")
        return {"message": "Scout profile deleted successfully"}
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting scout profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/")
async def search_scouts(
    organization: Optional[str] = Query(None, description="Organization filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for scouts and organizations
    """
    try:
        filters = {}
        
        if organization:
            filters["organization"] = organization
        if location:
            filters["location"] = location
        if sport:
            filters["sport"] = sport
        
        result = await scout_service.search_scouts(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return {
            "count": result["total"],
            "results": result["scouts"]
        }
        
    except Exception as e:
        logger.error(f"Error searching scouts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search", response_model=ScoutSearchResponse)
async def search_scouts(
    query: Optional[str] = Query(None, description="Search query"),
    sport: Optional[str] = Query(None, description="Sport filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    experience_years: Optional[int] = Query(None, description="Minimum experience years"),
    verified: Optional[bool] = Query(None, description="Verification status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """Search for scouts with filters"""
    try:
        filters = ScoutSearchFilters(
            query=query,
            sport=sport,
            location=location,
            experience_years=experience_years,
            verified=verified
        )
        
        result = await scout_service.search_scouts(
            filters=filters,
            page=page,
            limit=limit
        )
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching scouts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats", response_model=ScoutStatsResponse)
async def get_scout_stats(
    current_user: dict = Depends(require_scout_role)
):
    """Get current scout's statistics"""
    try:
        stats = await scout_service.get_stats(current_user["uid"])
        return stats
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Opportunity Management
@router.post("/opportunities", response_model=OpportunityResponse)
async def create_opportunity(
    opportunity: OpportunityCreate,
    current_user: dict = Depends(require_verified_scout)
):
    """Create a new opportunity"""
    try:
        result = await opportunity_service.create_opportunity(
            scout_id=current_user["uid"],
            opportunity_data=opportunity
        )
        logger.info(f"Opportunity created by scout {current_user['uid']}")
        return result
    except (ValidationError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/opportunities", response_model=List[OpportunityResponse])
async def get_scout_opportunities(
    status: Optional[str] = Query(None, description="Opportunity status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_scout_role)
):
    """Get opportunities created by current scout"""
    try:
        opportunities = await opportunity_service.get_scout_opportunities(
            scout_id=current_user["uid"],
            status=status,
            page=page,
            limit=limit
        )
        return opportunities
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def get_scout_opportunity(
    opportunity_id: str,
    current_user: dict = Depends(require_scout_role)
):
    """Get specific opportunity created by current scout"""
    try:
        opportunity = await opportunity_service.get_scout_opportunity(
            opportunity_id=opportunity_id,
            scout_id=current_user["uid"]
        )
        if not opportunity:
            raise ResourceNotFoundError("Opportunity not found")
        return opportunity
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
async def update_scout_opportunity(
    opportunity_id: str,
    opportunity: OpportunityUpdate,
    current_user: dict = Depends(require_verified_scout)
):
    """Update opportunity created by current scout"""
    try:
        result = await opportunity_service.update_scout_opportunity(
            opportunity_id=opportunity_id,
            scout_id=current_user["uid"],
            opportunity_data=opportunity
        )
        logger.info(f"Opportunity {opportunity_id} updated by scout {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating scout opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/opportunities/{opportunity_id}")
async def delete_scout_opportunity(
    opportunity_id: str,
    current_user: dict = Depends(require_verified_scout)
):
    """Delete opportunity created by current scout"""
    try:
        await opportunity_service.delete_scout_opportunity(
            opportunity_id=opportunity_id,
            scout_id=current_user["uid"]
        )
        logger.info(f"Opportunity {opportunity_id} deleted by scout {current_user['uid']}")
        return {"message": "Opportunity deleted successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting scout opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/opportunities/{opportunity_id}/applications")
async def get_opportunity_applications(
    opportunity_id: str,
    status: Optional[str] = Query(None, description="Application status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_scout_role)
):
    """Get applications for opportunity created by current scout"""
    try:
        applications = await opportunity_service.get_opportunity_applications(
            opportunity_id=opportunity_id,
            scout_id=current_user["uid"],
            status=status,
            page=page,
            limit=limit
        )
        return applications
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting opportunity applications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/opportunities/{opportunity_id}/applications/{application_id}")
async def update_application_status(
    opportunity_id: str,
    application_id: str,
    status: str = Form(..., description="New application status"),
    current_user: dict = Depends(require_verified_scout)
):
    """Update application status for opportunity created by current scout"""
    try:
        result = await opportunity_service.update_application_status(
            opportunity_id=opportunity_id,
            application_id=application_id,
            scout_id=current_user["uid"],
            status=status
        )
        logger.info(f"Application {application_id} status updated to {status} by scout {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Media Management
@router.post("/media", response_model=MediaResponse)
async def upload_scout_media(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: dict = Depends(require_scout_role)
):
    """Upload media for scout profile"""
    try:
        media_data = MediaCreate(
            title=title,
            description=description,
            tags=tags.split(",") if tags else []
        )
        
        result = await media_service.upload_media(
            user_id=current_user["uid"],
            user_type="scout",
            file=file,
            media_data=media_data
        )
        logger.info(f"Media uploaded by scout {current_user['uid']}")
        return result
    except (ValidationError, AuthenticationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading scout media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/media", response_model=List[MediaResponse])
async def get_scout_media(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_scout_role)
):
    """Get media uploaded by current scout"""
    try:
        media_list = await media_service.get_user_media(
            user_id=current_user["uid"],
            user_type="scout",
            page=page,
            limit=limit
        )
        return media_list
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting scout media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/media/{media_id}")
async def delete_scout_media(
    media_id: str,
    current_user: dict = Depends(require_scout_role)
):
    """Delete media uploaded by current scout"""
    try:
        await media_service.delete_user_media(
            media_id=media_id,
            user_id=current_user["uid"],
            user_type="scout"
        )
        logger.info(f"Media {media_id} deleted by scout {current_user['uid']}")
        return {"message": "Media deleted successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting scout media: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Verification
@router.post("/verification", response_model=VerificationDocumentResponse)
async def submit_verification(
    document: VerificationDocumentCreate,
    current_user: dict = Depends(require_scout_role)
):
    """Submit verification documents"""
    try:
        result = await scout_service.submit_verification(
            user_id=current_user["uid"],
            document_data=document
        )
        logger.info(f"Verification submitted by scout {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/verification/status")
async def get_verification_status(
    current_user: dict = Depends(require_scout_role)
):
    """Get verification status for current scout"""
    try:
        status = await scout_service.get_verification_status(current_user["uid"])
        return status
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting verification status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 

@router.get("/me/analytics")
async def get_my_analytics(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(require_scout_role)
):
    """
    Retrieve analytics for the authenticated scout
    """
    try:
        analytics = await scout_service.get_analytics(
            user_id=current_user["uid"],
            start_date=start_date,
            end_date=end_date
        )
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting scout analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/me/recommendations")
async def get_my_recommendations(
    sport: Optional[str] = Query(None, description="Sport filter"),
    position: Optional[str] = Query(None, description="Position filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_scout_role)
):
    """
    Retrieve personalized athlete recommendations for the scout
    Based on scout's profile, focus areas, and search history
    """
    try:
        filters = {}
        if sport:
            filters["sport"] = sport
        if position:
            filters["position"] = position
        if location:
            filters["location"] = location
        
        recommendations = await scout_service.get_athlete_recommendations(
            scout_id=current_user["uid"],
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error getting scout recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 