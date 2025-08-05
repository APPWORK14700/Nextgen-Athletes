from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Application(BaseModelWithID):
    """Application model for opportunities"""
    opportunity_id: str
    athlete_id: str
    status: Literal["pending", "accepted", "rejected", "withdrawn"] = "pending"
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    applied_at: datetime = Field(default_factory=datetime.utcnow)
    status_updated_at: Optional[datetime] = None


class ApplicationCreate(BaseModel):
    """Model for creating application"""
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None


class ApplicationUpdate(BaseModel):
    """Model for updating application"""
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None


class ApplicationStatusUpdate(BaseModel):
    """Model for updating application status"""
    status: Literal["accepted", "rejected"]
    feedback: Optional[str] = None


class ApplicationWithdrawRequest(BaseModel):
    """Model for withdrawing application"""
    reason: Optional[str] = None 