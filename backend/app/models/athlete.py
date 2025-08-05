from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class AthleteProfile(BaseModelWithID):
    """Athlete profile model"""
    user_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Literal["male", "female", "other"]
    location: str
    primary_sport_category_id: str
    secondary_sport_category_ids: Optional[List[str]] = []
    position: str
    height_cm: int = Field(..., ge=100, le=250)  # Reasonable height range
    weight_kg: int = Field(..., ge=30, le=200)   # Reasonable weight range
    academic_info: Optional[str] = None
    career_highlights: Optional[str] = None
    profile_image_url: Optional[str] = None


class AthleteProfileCreate(BaseModel):
    """Model for creating athlete profile"""
    first_name: str
    last_name: str
    date_of_birth: date
    gender: Literal["male", "female", "other"]
    location: str
    primary_sport_category_id: str
    secondary_sport_category_ids: Optional[List[str]] = []
    position: str
    height_cm: int = Field(..., ge=100, le=250)
    weight_kg: int = Field(..., ge=30, le=200)
    academic_info: Optional[str] = None
    career_highlights: Optional[str] = None


class AthleteProfileUpdate(BaseModel):
    """Model for updating athlete profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    location: Optional[str] = None
    primary_sport_category_id: Optional[str] = None
    secondary_sport_category_ids: Optional[List[str]] = None
    position: Optional[str] = None
    height_cm: Optional[int] = Field(None, ge=100, le=250)
    weight_kg: Optional[int] = Field(None, ge=30, le=200)
    academic_info: Optional[str] = None
    career_highlights: Optional[str] = None
    profile_image_url: Optional[str] = None


class AthleteSearchFilters(BaseModel):
    """Model for athlete search filters"""
    sport_category_id: Optional[str] = None
    position: Optional[str] = None
    min_age: Optional[int] = Field(None, ge=10, le=50)
    max_age: Optional[int] = Field(None, ge=10, le=50)
    gender: Optional[Literal["male", "female", "other"]] = None
    location: Optional[str] = None
    min_rating: Optional[Literal["exceptional", "excellent", "good", "developing", "needs_improvement"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AthleteAnalytics(BaseModel):
    """Model for athlete analytics"""
    profile_views: int = 0
    media_views: int = 0
    messages_received: int = 0
    opportunities_applied: int = 0
    applications_accepted: int = 0 