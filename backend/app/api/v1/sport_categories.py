"""
Sport Categories API endpoints for Athletes Networking App

This module provides endpoints for managing sport categories with dynamic stats fields.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.api.dependencies import get_current_user, require_admin_role
from app.services.sport_category_service import SportCategoryService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError

router = APIRouter(tags=["sport-categories"])

# Pydantic models for requests and responses
class ValidationRule(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    pattern: Optional[str] = None

class StatsField(BaseModel):
    key: str = Field(..., max_length=50)
    label: str = Field(..., max_length=100)
    type: str = Field(..., regex="^(integer|float|string|boolean)$")
    unit: Optional[str] = Field(None, max_length=20)
    required: bool = False
    default_value: Optional[Any] = None
    validation: Optional[ValidationRule] = None
    display_order: int = Field(..., ge=1)

class AchievementType(BaseModel):
    key: str = Field(..., max_length=50)
    label: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    icon_url: Optional[HttpUrl] = None

class SportCategoryRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    icon_url: Optional[HttpUrl] = None
    stats_fields: List[StatsField] = Field(..., min_items=1)
    achievement_types: List[AchievementType] = Field(default_factory=list)

class SportCategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[HttpUrl] = None
    stats_fields: Optional[List[StatsField]] = None
    achievement_types: Optional[List[AchievementType]] = None

class SportCategoryResponse(BaseModel):
    id: str
    name: str
    description: str
    icon_url: Optional[str] = None
    is_active: bool
    created_by: str
    created_at: str
    updated_at: str
    stats_fields: List[StatsField]
    achievement_types: List[AchievementType]

class SportCategoryListResponse(BaseResponse):
    categories: List[SportCategoryResponse]
    total: int
    page: int
    limit: int

class StatsTemplateResponse(BaseModel):
    category: SportCategoryResponse
    stats_template: Dict[str, Any]
    achievement_types: List[AchievementType]

# Initialize services
sport_category_service = SportCategoryService()

@router.post("/admin/sport-categories", response_model=SportCategoryResponse, status_code=201)
async def create_sport_category(
    request: SportCategoryRequest,
    current_user: dict = Depends(require_admin_role)
):
    """
    Create a new sport category with predefined stats fields and achievement types
    Only available to administrators
    """
    try:
        # Validate that stats field keys are unique
        field_keys = [field.key for field in request.stats_fields]
        if len(field_keys) != len(set(field_keys)):
            raise ValidationError("Stats field keys must be unique")
        
        # Validate that achievement type keys are unique
        achievement_keys = [achievement.key for achievement in request.achievement_types]
        if len(achievement_keys) != len(set(achievement_keys)):
            raise ValidationError("Achievement type keys must be unique")
        
        # Check if sport category with same name exists
        existing = await sport_category_service.get_category_by_name(request.name)
        if existing:
            raise ValidationError(f"Sport category with name '{request.name}' already exists")
        
        # Create sport category
        category_data = request.dict()
        category_data["created_by"] = current_user["uid"]
        category_data["is_active"] = True
        
        result = await sport_category_service.create_category(category_data)
        
        return SportCategoryResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sport category: {str(e)}"
        )

@router.get("/sport-categories", response_model=SportCategoryListResponse)
async def list_active_sport_categories(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List all active sport categories
    Available to all authenticated users
    """
    try:
        result = await sport_category_service.get_active_categories(
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return SportCategoryListResponse(
            categories=[SportCategoryResponse(**cat) for cat in result["categories"]],
            total=result["total"],
            page=(offset // limit) + 1,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sport categories: {str(e)}"
        )

@router.get("/admin/sport-categories", response_model=SportCategoryListResponse)
async def list_all_sport_categories(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_admin_role)
):
    """
    List all sport categories (including inactive ones)
    Only available to administrators
    """
    try:
        filters = {}
        if is_active is not None:
            filters["is_active"] = is_active
        
        result = await sport_category_service.get_all_categories(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return SportCategoryListResponse(
            categories=[SportCategoryResponse(**cat) for cat in result["categories"]],
            total=result["total"],
            page=(offset // limit) + 1,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sport categories: {str(e)}"
        )

@router.get("/sport-categories/{category_id}", response_model=SportCategoryResponse)
async def get_sport_category(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve a specific sport category
    Available to all authenticated users
    """
    try:
        result = await sport_category_service.get_category_by_id(category_id)
        
        return SportCategoryResponse(**result)
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sport category not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sport category: {str(e)}"
        )

@router.put("/admin/sport-categories/{category_id}", response_model=SportCategoryResponse)
async def update_sport_category(
    category_id: str,
    request: SportCategoryUpdateRequest,
    current_user: dict = Depends(require_admin_role)
):
    """
    Update a sport category
    Only available to administrators
    """
    try:
        # Verify category exists
        existing = await sport_category_service.get_category_by_id(category_id)
        
        # Validate stats field keys are unique if provided
        if request.stats_fields:
            field_keys = [field.key for field in request.stats_fields]
            if len(field_keys) != len(set(field_keys)):
                raise ValidationError("Stats field keys must be unique")
        
        # Validate achievement type keys are unique if provided
        if request.achievement_types:
            achievement_keys = [achievement.key for achievement in request.achievement_types]
            if len(achievement_keys) != len(set(achievement_keys)):
                raise ValidationError("Achievement type keys must be unique")
        
        # Check name conflict if name is being changed
        if request.name and request.name != existing["name"]:
            name_conflict = await sport_category_service.get_category_by_name(request.name)
            if name_conflict and name_conflict["id"] != category_id:
                raise ValidationError(f"Sport category with name '{request.name}' already exists")
        
        # Update category
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        update_data["updated_by"] = current_user["uid"]
        
        result = await sport_category_service.update_category(category_id, update_data)
        
        return SportCategoryResponse(**result)
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sport category not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update sport category: {str(e)}"
        )

@router.delete("/admin/sport-categories/{category_id}")
async def deactivate_sport_category(
    category_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """
    Deactivate a sport category (soft delete)
    Only available to administrators
    """
    try:
        # Verify category exists
        await sport_category_service.get_category_by_id(category_id)
        
        # Check if category is being used
        usage_count = await sport_category_service.get_category_usage_count(category_id)
        if usage_count > 0:
            raise ValidationError(
                f"Cannot deactivate sport category: {usage_count} records are using this category"
            )
        
        # Deactivate category
        await sport_category_service.deactivate_category(category_id)
        
        return {"message": "Sport category deactivated successfully"}
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sport category not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate sport category: {str(e)}"
        )

@router.post("/admin/sport-categories/{category_id}/activate")
async def activate_sport_category(
    category_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """
    Reactivate a deactivated sport category
    Only available to administrators
    """
    try:
        result = await sport_category_service.activate_category(category_id)
        
        return {"message": "Sport category activated successfully", "category": result}
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sport category not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate sport category: {str(e)}"
        )

@router.get("/sport-categories/{category_id}/stats-template", response_model=StatsTemplateResponse)
async def get_stats_template(
    category_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve the stats template for a sport category
    Available to all authenticated users
    """
    try:
        category = await sport_category_service.get_category_by_id(category_id)
        
        # Generate empty stats template based on stats fields
        stats_template = {}
        for field in category["stats_fields"]:
            if field["default_value"] is not None:
                stats_template[field["key"]] = field["default_value"]
            elif field["type"] == "integer":
                stats_template[field["key"]] = 0
            elif field["type"] == "float":
                stats_template[field["key"]] = 0.0
            elif field["type"] == "boolean":
                stats_template[field["key"]] = False
            else:  # string
                stats_template[field["key"]] = ""
        
        return StatsTemplateResponse(
            category=SportCategoryResponse(**category),
            stats_template=stats_template,
            achievement_types=category["achievement_types"]
        )
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sport category not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats template: {str(e)}"
        )

@router.get("/sport-categories/search/suggestions")
async def get_sport_category_suggestions(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=20),
    current_user: dict = Depends(get_current_user)
):
    """
    Get sport category suggestions for autocomplete
    Available to all authenticated users
    """
    try:
        result = await sport_category_service.search_category_suggestions(
            query=query,
            limit=limit
        )
        
        return {
            "suggestions": [
                {
                    "id": cat["id"],
                    "name": cat["name"],
                    "description": cat["description"],
                    "icon_url": cat.get("icon_url")
                }
                for cat in result
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sport category suggestions: {str(e)}"
        ) 