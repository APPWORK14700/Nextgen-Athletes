from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Flag(BaseModelWithID):
    """Flag model for content moderation"""
    content_id: str
    content_type: Literal["media", "opportunity", "profile"]
    reporter_id: str
    reason: Literal["inappropriate_content", "fake_profile", "spam", "harassment", "copyright", "other"]
    description: Optional[str] = None
    evidence_url: Optional[str] = None
    status: Literal["pending", "resolved", "dismissed"] = "pending"
    resolved_at: Optional[datetime] = None


class FlagCreate(BaseModel):
    """Model for creating flag"""
    reason: Literal["inappropriate_content", "fake_profile", "spam", "harassment", "copyright", "other"]
    description: Optional[str] = None
    evidence_url: Optional[str] = None


class FlagResolve(BaseModel):
    """Model for resolving flag"""
    action: Literal["dismiss", "take_action"]
    notes: Optional[str] = None


class FlagSearchFilters(BaseModel):
    """Model for flag search filters"""
    status: Optional[Literal["pending", "resolved", "dismissed"]] = None
    content_type: Optional[Literal["media", "opportunity", "profile"]] = None
    reason: Optional[Literal["inappropriate_content", "fake_profile", "spam", "harassment", "copyright", "other"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0) 