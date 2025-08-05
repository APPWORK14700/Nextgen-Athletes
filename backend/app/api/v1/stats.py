"""
Stats API endpoints for Athletes Networking App

This module provides endpoints for managing athlete statistics and achievements.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, require_athlete_role, require_scout_role
from app.services.athlete_service import AthleteService
from app.services.stats_service import StatsService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/athletes", tags=["stats"])

# Pydantic models for requests and responses
class Achievement(BaseModel):
    type: str = Field(..., description="Achievement type key")
    title: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    date_achieved: str = Field(..., description="Date in YYYY-MM-DD format")
    evidence_url: Optional[str] = None

class StatsRequest(BaseModel):
    sport_category_id: str
    season: str = Field(..., max_length=50)
    team_name: Optional[str] = Field(None, max_length=100)
    league: Optional[str] = Field(None, max_length=100)
    position: Optional[str] = Field(None, max_length=50)
    stats: Dict[str, Any] = Field(..., description="Dynamic stats based on sport category")
    achievements: List[Achievement] = Field(default_factory=list)

class StatsUpdateRequest(BaseModel):
    sport_category_id: Optional[str] = None
    season: Optional[str] = None
    team_name: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    achievements: Optional[List[Achievement]] = None

class StatsResponse(BaseModel):
    id: str
    athlete_id: str
    sport_category_id: str
    season: str
    team_name: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    stats: Dict[str, Any]
    achievements: List[Achievement]
    created_at: str
    updated_at: str

class StatsListResponse(BaseResponse):
    stats: List[StatsResponse]
    count: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool

# Initialize services
athlete_service = AthleteService()
stats_service = StatsService()

@router.post("/me/stats", response_model=StatsResponse, status_code=201)
async def create_athlete_stats(
    request: StatsRequest,
    current_user: dict = Depends(require_athlete_role)
):
    """
    Create or update athlete statistics
    Only available to athletes for their own profile
    """
    try:
        # Validate sport category exists
        await stats_service.validate_sport_category(request.sport_category_id)
        
        # Validate stats against sport category schema
        await stats_service.validate_stats_data(
            sport_category_id=request.sport_category_id,
            stats_data=request.stats
        )
        
        # Create stats record
        stats_data = request.dict()
        stats_data["athlete_id"] = current_user["uid"]
        
        result = await stats_service.create_stats(stats_data)
        
        return StatsResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create stats: {str(e)}"
        )

@router.get("/me/stats", response_model=StatsListResponse)
async def get_my_stats(
    sport_category_id: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(require_athlete_role)
):
    """
    Retrieve paginated stats for the authenticated athlete
    """
    try:
        filters = {}
        
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        if season:
            filters["season"] = season
        
        result = await stats_service.get_athlete_stats(
            athlete_id=current_user["uid"],
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return StatsListResponse(
            stats=[StatsResponse(**stat) for stat in result["results"]],
            count=result["count"],
            limit=result["limit"],
            offset=result["offset"],
            has_next=result["has_next"],
            has_previous=result["has_previous"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )

@router.get("/{athlete_id}/stats", response_model=StatsListResponse)
async def get_athlete_stats(
    athlete_id: str,
    sport_category_id: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user: dict = Depends(require_scout_role)
):
    """
    Retrieve paginated stats for a specific athlete
    Only available to verified scouts
    """
    try:
        # Verify athlete exists
        await athlete_service.get_profile_by_user_id(athlete_id)
        
        filters = {}
        
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        if season:
            filters["season"] = season
        
        result = await stats_service.get_athlete_stats(
            athlete_id=athlete_id,
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return StatsListResponse(
            stats=[StatsResponse(**stat) for stat in result["results"]],
            count=result["count"],
            limit=result["limit"],
            offset=result["offset"],
            has_next=result["has_next"],
            has_previous=result["has_previous"]
        )
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )

@router.put("/me/stats/{stats_id}", response_model=StatsResponse)
async def update_athlete_stats(
    stats_id: str,
    request: StatsUpdateRequest,
    current_user: dict = Depends(require_athlete_role)
):
    """
    Update athlete statistics
    Only the athlete who owns the stats can update them
    """
    try:
        # Verify stats ownership
        existing_stats = await stats_service.get_stats_by_id(stats_id)
        if existing_stats["athlete_id"] != current_user["uid"]:
            raise AuthorizationError("You can only update your own stats")
        
        # Validate sport category if provided
        if request.sport_category_id:
            await stats_service.validate_sport_category(request.sport_category_id)
        
        # Validate stats data if provided
        if request.stats:
            sport_category_id = request.sport_category_id or existing_stats["sport_category_id"]
            await stats_service.validate_stats_data(
                sport_category_id=sport_category_id,
                stats_data=request.stats
            )
        
        # Update stats
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        result = await stats_service.update_stats(stats_id, update_data)
        
        return StatsResponse(**result)
        
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
            detail="Stats record not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update stats: {str(e)}"
        )

@router.delete("/me/stats/{stats_id}", status_code=204)
async def delete_athlete_stats(
    stats_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """
    Delete athlete statistics
    Only the athlete who owns the stats can delete them
    """
    try:
        # Verify stats ownership
        existing_stats = await stats_service.get_stats_by_id(stats_id)
        if existing_stats["athlete_id"] != current_user["uid"]:
            raise AuthorizationError("You can only delete your own stats")
        
        # Delete stats
        await stats_service.delete_stats(stats_id)
        
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stats record not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete stats: {str(e)}"
        )

@router.get("/me/stats/summary")
async def get_my_stats_summary(
    current_user: dict = Depends(require_athlete_role)
):
    """
    Get a summary of athlete's stats across all sports and seasons
    """
    try:
        result = await stats_service.get_athlete_stats_summary(current_user["uid"])
        
        return {
            "athlete_id": current_user["uid"],
            "total_seasons": result["total_seasons"],
            "sports_played": result["sports_played"],
            "achievements_count": result["achievements_count"],
            "recent_stats": result["recent_stats"],
            "performance_trends": result["performance_trends"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats summary: {str(e)}"
        )

@router.get("/{athlete_id}/stats/summary")
async def get_athlete_stats_summary(
    athlete_id: str,
    current_user: dict = Depends(require_scout_role)
):
    """
    Get a summary of specified athlete's stats
    Only available to verified scouts
    """
    try:
        # Verify athlete exists
        await athlete_service.get_profile_by_user_id(athlete_id)
        
        result = await stats_service.get_athlete_stats_summary(athlete_id)
        
        return {
            "athlete_id": athlete_id,
            "total_seasons": result["total_seasons"],
            "sports_played": result["sports_played"],
            "achievements_count": result["achievements_count"],
            "recent_stats": result["recent_stats"],
            "performance_trends": result["performance_trends"]
        }
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats summary: {str(e)}"
        ) 