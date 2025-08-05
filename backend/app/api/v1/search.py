"""
Search API endpoints for Athletes Networking App

This module provides advanced search functionality and search history management.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, require_scout_role, require_athlete_role
from app.services.athlete_service import AthleteService
from app.services.opportunity_service import OpportunityService
from app.services.search_service import SearchService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError

router = APIRouter(prefix="/search", tags=["search"])

# Pydantic models for requests and responses
class AgeRange(BaseModel):
    min: int = Field(..., ge=13, le=50)
    max: int = Field(..., ge=13, le=50)

class DateRange(BaseModel):
    start: str = Field(..., description="Start date in YYYY-MM-DD format")
    end: str = Field(..., description="End date in YYYY-MM-DD format")

class AdvancedAthleteSearchRequest(BaseModel):
    sport_category_id: Optional[str] = None
    position: Optional[str] = None
    age_range: Optional[AgeRange] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    rating: Optional[str] = None
    stats_filters: Optional[Dict[str, Any]] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

class AdvancedOpportunitySearchRequest(BaseModel):
    type: Optional[str] = None
    location: Optional[str] = None
    date_range: Optional[DateRange] = None
    sport_category_id: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

class SearchHistoryResponse(BaseModel):
    id: str
    user_id: str
    search_type: str
    query: str
    filters: Dict[str, Any]
    created_at: str

class SearchHistoryListResponse(BaseResponse):
    searches: List[SearchHistoryResponse]
    total: int
    page: int
    limit: int

class AthleteSearchResult(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    sport: str
    position: Optional[str] = None
    location: Optional[str] = None
    rating: Optional[str] = None
    profile_image_url: Optional[str] = None

class OpportunitySearchResult(BaseModel):
    id: str
    title: str
    description: str
    type: str
    location: str
    sport_category_id: str
    created_at: str

class AdvancedAthleteSearchResponse(BaseResponse):
    count: int
    results: List[AthleteSearchResult]

class AdvancedOpportunitySearchResponse(BaseResponse):
    count: int
    results: List[OpportunitySearchResult]

# Initialize services
athlete_service = AthleteService()
opportunity_service = OpportunityService()
search_service = SearchService()

@router.post("/athletes", response_model=AdvancedAthleteSearchResponse)
async def advanced_athlete_search(
    request: AdvancedAthleteSearchRequest,
    current_user: dict = Depends(require_scout_role)
):
    """
    Advanced athlete search with complex filters
    Restricted to verified scouts only
    """
    try:
        # Convert request to search filters
        filters = {}
        
        if request.sport_category_id:
            filters["sport_category_id"] = request.sport_category_id
        if request.position:
            filters["position"] = request.position
        if request.gender:
            filters["gender"] = request.gender
        if request.location:
            filters["location"] = request.location
        if request.rating:
            filters["min_rating"] = request.rating
        if request.age_range:
            filters["min_age"] = request.age_range.min
            filters["max_age"] = request.age_range.max
        if request.stats_filters:
            filters["stats_filters"] = request.stats_filters
        
        # Perform search
        search_result = await athlete_service.search_athletes(
            filters=filters,
            page=(request.offset // request.limit) + 1,
            limit=request.limit
        )
        
        # Save search to history
        await search_service.save_search(
            user_id=current_user["uid"],
            search_type="athletes",
            query="",
            filters=filters
        )
        
        return AdvancedAthleteSearchResponse(
            count=search_result["total"],
            results=[AthleteSearchResult(**athlete) for athlete in search_result["athletes"]]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.post("/opportunities", response_model=AdvancedOpportunitySearchResponse)
async def advanced_opportunity_search(
    request: AdvancedOpportunitySearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Advanced opportunity search with complex filters
    Available to all authenticated users
    """
    try:
        # Convert request to search filters
        filters = {}
        
        if request.type:
            filters["type"] = request.type
        if request.location:
            filters["location"] = request.location
        if request.sport_category_id:
            filters["sport_category_id"] = request.sport_category_id
        if request.date_range:
            filters["start_date_gte"] = request.date_range.start
            filters["end_date_lte"] = request.date_range.end
        
        # Perform search
        search_result = await opportunity_service.search_opportunities(
            filters=filters,
            page=(request.offset // request.limit) + 1,
            limit=request.limit
        )
        
        # Save search to history
        await search_service.save_search(
            user_id=current_user["uid"],
            search_type="opportunities",
            query="",
            filters=filters
        )
        
        return AdvancedOpportunitySearchResponse(
            count=search_result["total"],
            results=[OpportunitySearchResult(**opp) for opp in search_result["opportunities"]]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.get("/history", response_model=SearchHistoryListResponse)
async def get_search_history(
    search_type: Optional[str] = Query(None, description="Filter by search type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve search history for the authenticated user
    """
    try:
        result = await search_service.get_user_search_history(
            user_id=current_user["uid"],
            search_type=search_type,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return SearchHistoryListResponse(
            searches=[SearchHistoryResponse(**search) for search in result["searches"]],
            total=result["total"],
            page=(offset // limit) + 1,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve search history: {str(e)}"
        )

@router.delete("/history/{search_id}")
async def delete_search_history_item(
    search_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific search from history
    """
    try:
        await search_service.delete_search_history_item(
            search_id=search_id,
            user_id=current_user["uid"]
        )
        
        return {"message": "Search history item deleted successfully"}
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Search history item not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete search history item: {str(e)}"
        )

@router.delete("/history")
async def clear_search_history(
    current_user: dict = Depends(get_current_user)
):
    """
    Clear all search history for the authenticated user
    """
    try:
        await search_service.clear_user_search_history(current_user["uid"])
        
        return {"message": "Search history cleared successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear search history: {str(e)}"
        ) 