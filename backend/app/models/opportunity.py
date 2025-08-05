from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Opportunity(BaseModelWithID):
    """Opportunity model for trials, scholarships, contracts"""
    scout_id: str
    title: str
    description: str
    type: Literal["trial", "scholarship", "contract"]
    sport_category_id: str
    location: str
    start_date: date
    end_date: Optional[date] = None
    requirements: Optional[str] = None
    compensation: Optional[str] = None
    is_active: bool = True
    moderation_status: Literal["pending", "approved", "rejected"] = "pending"


class OpportunityCreate(BaseModel):
    """Model for creating opportunity"""
    title: str
    description: str
    type: Literal["trial", "scholarship", "contract"]
    sport_category_id: str
    location: str
    start_date: date
    end_date: Optional[date] = None
    requirements: Optional[str] = None
    compensation: Optional[str] = None


class OpportunityUpdate(BaseModel):
    """Model for updating opportunity"""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[Literal["trial", "scholarship", "contract"]] = None
    sport_category_id: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    requirements: Optional[str] = None
    compensation: Optional[str] = None
    is_active: Optional[bool] = None


class OpportunitySearchFilters(BaseModel):
    """Model for opportunity search filters"""
    type: Optional[Literal["trial", "scholarship", "contract"]] = None
    location: Optional[str] = None
    sport_category_id: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class OpportunityToggleRequest(BaseModel):
    """Model for toggling opportunity status"""
    is_active: bool 