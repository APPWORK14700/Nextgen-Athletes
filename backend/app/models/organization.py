from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Organization(BaseModelWithID):
    """Organization model for clubs, schools, universities, agencies"""
    name: str
    type: Literal["club", "school", "university", "agency", "other"]
    location: str
    website: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_verified: bool = False


class OrganizationCreate(BaseModel):
    """Model for creating organization"""
    name: str
    type: Literal["club", "school", "university", "agency", "other"]
    location: str
    website: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None


class OrganizationUpdate(BaseModel):
    """Model for updating organization"""
    name: Optional[str] = None
    type: Optional[Literal["club", "school", "university", "agency", "other"]] = None
    location: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_verified: Optional[bool] = None


class OrganizationSearchFilters(BaseModel):
    """Model for organization search filters"""
    type: Optional[Literal["club", "school", "university", "agency", "other"]] = None
    location: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0) 