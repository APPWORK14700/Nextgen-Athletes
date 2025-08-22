"""
Response models for media operations
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AIAnalysisResponse(BaseModel):
    """AI analysis response model"""
    status: str = Field(..., description="Analysis status")
    rating: Optional[float] = Field(None, description="AI rating score")
    summary: Optional[str] = Field(None, description="Brief summary of analysis")
    detailed_analysis: Optional[Dict[str, Any]] = Field(None, description="Detailed analysis results")
    sport_specific_metrics: Optional[Dict[str, Any]] = Field(None, description="Sport-specific metrics")
    confidence_score: Optional[float] = Field(None, description="AI confidence score")
    analysis_started_at: Optional[str] = Field(None, description="When analysis started")
    analysis_completed_at: Optional[str] = Field(None, description="When analysis completed")
    retry_count: int = Field(0, description="Number of retry attempts")
    max_retries: int = Field(5, description="Maximum retry attempts")
    next_retry_at: Optional[str] = Field(None, description="Next retry timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class MediaResponse(BaseModel):
    """Media response model"""
    id: str = Field(..., description="Media ID")
    athlete_id: str = Field(..., description="Athlete ID")
    type: str = Field(..., description="Media type")
    url: str = Field(..., description="Media file URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    description: Optional[str] = Field(None, description="Media description")
    moderation_status: str = Field(..., description="Moderation status")
    created_at: str = Field(..., description="Creation timestamp")
    ai_analysis: AIAnalysisResponse = Field(..., description="AI analysis results")


class MediaStatusResponse(BaseModel):
    """Media status response model"""
    media_id: str = Field(..., description="Media ID")
    ai_analysis: AIAnalysisResponse = Field(..., description="AI analysis status")


class BulkUploadResponse(BaseModel):
    """Bulk upload response model"""
    uploaded_count: int = Field(..., description="Number of successfully uploaded files")
    failed_count: int = Field(..., description="Number of failed uploads")
    media_ids: List[str] = Field(..., description="IDs of uploaded media")
    errors: List[str] = Field(..., description="List of error messages")


class MediaListResponse(BaseModel):
    """Media list response model"""
    media: List[MediaResponse] = Field(..., description="List of media items")
    total_count: int = Field(..., description="Total number of media items")
    limit: int = Field(..., description="Requested limit")
    offset: int = Field(..., description="Requested offset")


class RecommendationResponse(BaseModel):
    """Recommendation response model"""
    media: List[MediaResponse] = Field(..., description="Recommended media items")
    total_count: int = Field(..., description="Total number of recommendations")
    algorithm: str = Field(..., description="Algorithm used for recommendations")
    confidence: float = Field(..., description="Overall confidence in recommendations")


class UploadRateLimitInfo(BaseModel):
    """Upload rate limit information"""
    current_uploads: int = Field(..., description="Current uploads in time window")
    max_uploads: int = Field(..., description="Maximum allowed uploads")
    time_window_hours: int = Field(..., description="Time window in hours")
    reset_time: datetime = Field(..., description="When rate limit resets") 