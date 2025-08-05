from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class ScoutProfile(BaseModelWithID):
    """Scout profile model"""
    user_id: str
    first_name: str
    last_name: str
    organization: str
    title: str
    verification_status: Literal["pending", "verified", "rejected"] = "pending"
    focus_areas: List[str] = []


class ScoutProfileCreate(BaseModel):
    """Model for creating scout profile"""
    first_name: str
    last_name: str
    organization: str
    title: str
    focus_areas: Optional[List[str]] = []


class ScoutProfileUpdate(BaseModel):
    """Model for updating scout profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization: Optional[str] = None
    title: Optional[str] = None
    focus_areas: Optional[List[str]] = None


class ScoutSearchFilters(BaseModel):
    """Model for scout search filters"""
    organization: Optional[str] = None
    location: Optional[str] = None
    sport: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ScoutAnalytics(BaseModel):
    """Model for scout analytics"""
    athletes_viewed: int = 0
    searches_performed: int = 0
    opportunities_created: int = 0
    applications_received: int = 0
    messages_sent: int = 0


class ScoutVerificationRequest(BaseModel):
    """Model for scout verification request"""
    status: Literal["verified", "rejected"]
    notes: Optional[str] = None 