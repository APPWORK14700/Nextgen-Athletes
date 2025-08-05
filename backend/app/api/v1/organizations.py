"""
Organizations API endpoints for Athletes Networking App

This module provides endpoints for managing organizations (clubs, schools, agencies, etc.).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.api.dependencies import get_current_user, require_admin_role
from app.services.organization_service import OrganizationService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/organizations", tags=["organizations"])

# Pydantic models for requests and responses
class OrganizationRequest(BaseModel):
    name: str = Field(..., max_length=200)
    type: str = Field(..., regex="^(club|school|university|agency|other)$")
    location: str = Field(..., max_length=200)
    website: Optional[HttpUrl] = None
    description: str = Field(..., max_length=1000)
    logo_url: Optional[HttpUrl] = None

class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    type: Optional[str] = Field(None, regex="^(club|school|university|agency|other)$")
    location: Optional[str] = Field(None, max_length=200)
    website: Optional[HttpUrl] = None
    description: Optional[str] = Field(None, max_length=1000)
    logo_url: Optional[HttpUrl] = None

class OrganizationResponse(BaseModel):
    id: str
    name: str
    type: str
    location: str
    website: Optional[str] = None
    description: str
    logo_url: Optional[str] = None
    is_verified: bool
    created_at: str

class OrganizationListResponse(BaseResponse):
    organizations: List[OrganizationResponse]
    total: int
    page: int
    limit: int

# Initialize services
organization_service = OrganizationService()

@router.post("/", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    request: OrganizationRequest,
    current_user: dict = Depends(require_admin_role)
):
    """
    Create a new organization
    Only available to administrators
    """
    try:
        # Check if organization with same name exists
        existing = await organization_service.get_organization_by_name(request.name)
        if existing:
            raise ValidationError(f"Organization with name '{request.name}' already exists")
        
        # Create organization
        org_data = request.dict()
        org_data["created_by"] = current_user["uid"]
        org_data["is_verified"] = True  # Organizations created by admin are auto-verified
        
        result = await organization_service.create_organization(org_data)
        
        return OrganizationResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create organization: {str(e)}"
        )

@router.get("/", response_model=OrganizationListResponse)
async def list_organizations(
    type: Optional[str] = Query(None, description="Filter by organization type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    verified_only: bool = Query(True, description="Show only verified organizations"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List all organizations with optional filters
    Available to all authenticated users
    """
    try:
        filters = {}
        
        if type:
            if type not in ["club", "school", "university", "agency", "other"]:
                raise ValidationError("Invalid organization type")
            filters["type"] = type
            
        if location:
            filters["location"] = location
            
        if verified_only:
            filters["is_verified"] = True
        
        result = await organization_service.search_organizations(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return OrganizationListResponse(
            organizations=[OrganizationResponse(**org) for org in result["organizations"]],
            total=result["total"],
            page=(offset // limit) + 1,
            limit=limit
        )
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve organizations: {str(e)}"
        )

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve a specific organization by ID
    Available to all authenticated users
    """
    try:
        result = await organization_service.get_organization_by_id(organization_id)
        
        return OrganizationResponse(**result)
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve organization: {str(e)}"
        )

@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    request: OrganizationUpdateRequest,
    current_user: dict = Depends(require_admin_role)
):
    """
    Update an organization
    Only available to administrators
    """
    try:
        # Verify organization exists
        existing = await organization_service.get_organization_by_id(organization_id)
        
        # Check if name change conflicts with existing organization
        if request.name and request.name != existing["name"]:
            name_conflict = await organization_service.get_organization_by_name(request.name)
            if name_conflict and name_conflict["id"] != organization_id:
                raise ValidationError(f"Organization with name '{request.name}' already exists")
        
        # Update organization
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        update_data["updated_by"] = current_user["uid"]
        
        result = await organization_service.update_organization(organization_id, update_data)
        
        return OrganizationResponse(**result)
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update organization: {str(e)}"
        )

@router.delete("/{organization_id}")
async def delete_organization(
    organization_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """
    Delete an organization (soft delete - marks as inactive)
    Only available to administrators
    """
    try:
        # Verify organization exists
        await organization_service.get_organization_by_id(organization_id)
        
        # Check if organization has associated users/scouts
        usage_count = await organization_service.get_organization_usage_count(organization_id)
        if usage_count > 0:
            raise ValidationError(
                f"Cannot delete organization: {usage_count} users are associated with this organization"
            )
        
        # Soft delete organization
        await organization_service.deactivate_organization(organization_id)
        
        return {"message": "Organization deleted successfully"}
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete organization: {str(e)}"
        )

@router.post("/{organization_id}/verify")
async def verify_organization(
    organization_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """
    Verify an organization
    Only available to administrators
    """
    try:
        result = await organization_service.verify_organization(
            organization_id=organization_id,
            verified_by=current_user["uid"]
        )
        
        return {"message": "Organization verified successfully", "organization": result}
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify organization: {str(e)}"
        )

@router.get("/search/suggestions")
async def get_organization_suggestions(
    query: str = Query(..., min_length=2, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by organization type"),
    limit: int = Query(10, ge=1, le=20),
    current_user: dict = Depends(get_current_user)
):
    """
    Get organization suggestions for autocomplete
    Available to all authenticated users
    """
    try:
        filters = {"is_verified": True}
        
        if type:
            if type not in ["club", "school", "university", "agency", "other"]:
                raise ValidationError("Invalid organization type")
            filters["type"] = type
        
        result = await organization_service.search_organization_suggestions(
            query=query,
            filters=filters,
            limit=limit
        )
        
        return {
            "suggestions": [
                {
                    "id": org["id"],
                    "name": org["name"],
                    "type": org["type"],
                    "location": org["location"]
                }
                for org in result
            ]
        }
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get organization suggestions: {str(e)}"
        )

@router.get("/{organization_id}/stats")
async def get_organization_stats(
    organization_id: str,
    current_user: dict = Depends(require_admin_role)
):
    """
    Get statistics for an organization
    Only available to administrators
    """
    try:
        result = await organization_service.get_organization_stats(organization_id)
        
        return {
            "organization_id": organization_id,
            "total_scouts": result["total_scouts"],
            "verified_scouts": result["verified_scouts"],
            "total_opportunities": result["total_opportunities"],
            "active_opportunities": result["active_opportunities"],
            "total_applications": result["total_applications"],
            "recent_activity": result["recent_activity"]
        }
        
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve organization stats: {str(e)}"
        ) 