from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


class BaseModelWithID(BaseModel):
    """Base model with common fields for all entities"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        # Use the new serialization approach for datetime
        from_attributes = True
    )


class BaseResponse(BaseModel):
    """Base response model for API endpoints"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    """Generic paginated response model"""
    count: int
    results: list
    next: Optional[str] = None
    previous: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: dict = Field(
        ...,
        description="Error details containing code, message, and optional details"
    )


class SuccessResponse(BaseModel):
    """Standard success response model"""
    message: str
    data: Optional[dict] = None 