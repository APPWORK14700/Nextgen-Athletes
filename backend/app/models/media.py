from datetime import datetime
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class AIAnalysis(BaseModel):
    """AI analysis results for media"""
    status: Literal["pending", "processing", "completed", "failed", "retrying"] = "pending"
    rating: Optional[Literal["exceptional", "excellent", "good", "developing", "needs_improvement"]] = None
    summary: Optional[str] = None
    detailed_analysis: Optional[Dict[str, float]] = None  # technical_skills, physical_attributes, etc.
    sport_specific_metrics: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    analysis_started_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 5
    next_retry_at: Optional[datetime] = None
    error_message: Optional[str] = None


class Media(BaseModelWithID):
    """Media model for athlete videos, images, and reels"""
    athlete_id: str
    type: Literal["video", "image", "reel"]
    url: str
    thumbnail_url: Optional[str] = None
    moderation_status: Literal["pending", "approved", "rejected"] = "pending"
    ai_analysis: AIAnalysis = Field(default_factory=AIAnalysis)


class MediaCreate(BaseModel):
    """Model for creating media"""
    type: Literal["video", "image", "reel"]
    description: Optional[str] = None


class MediaUpdate(BaseModel):
    """Model for updating media"""
    description: Optional[str] = None


class MediaUploadResponse(BaseModel):
    """Response model for media upload"""
    media_id: str
    upload_url: str
    status: str = "pending"


class MediaBulkUploadRequest(BaseModel):
    """Model for bulk media upload"""
    files: list
    metadata: list


class MediaBulkUploadResponse(BaseModel):
    """Response model for bulk media upload"""
    uploaded_count: int
    failed_count: int
    media_ids: list[str]
    errors: list[str] = [] 