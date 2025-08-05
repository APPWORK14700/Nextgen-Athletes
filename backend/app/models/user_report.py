from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class UserReport(BaseModelWithID):
    """User report model for reporting inappropriate behavior"""
    reporter_id: str
    reported_user_id: str
    reason: Literal["harassment", "spam", "fake_profile", "inappropriate_content", "other"]
    description: str
    evidence_url: Optional[str] = None
    status: Literal["pending", "resolved", "dismissed"] = "pending"
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class UserReportCreate(BaseModel):
    """Model for creating user report"""
    reason: Literal["harassment", "spam", "fake_profile", "inappropriate_content", "other"]
    description: str
    evidence_url: Optional[str] = None


class UserReportResolve(BaseModel):
    """Model for resolving user report"""
    action: Literal["dismiss", "warn_user", "suspend_user", "delete_user"]
    notes: Optional[str] = None


class UserReportSearchFilters(BaseModel):
    """Model for user report search filters"""
    status: Optional[Literal["pending", "resolved", "dismissed"]] = None
    reason: Optional[Literal["harassment", "spam", "fake_profile", "inappropriate_content", "other"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0) 