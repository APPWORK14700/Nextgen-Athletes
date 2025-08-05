from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class VerificationDocument(BaseModelWithID):
    """Verification document model"""
    user_id: str
    document_type: Literal["id_card", "passport", "school_id", "other"]
    document_url: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    additional_info: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class VerificationDocumentCreate(BaseModel):
    """Model for creating verification document"""
    document_type: Literal["id_card", "passport", "school_id", "other"]
    document_url: str
    additional_info: Optional[str] = None


class VerificationDocumentReview(BaseModel):
    """Model for reviewing verification document"""
    status: Literal["approved", "rejected"]
    notes: Optional[str] = None


class VerificationDocumentSearchFilters(BaseModel):
    """Model for verification document search filters"""
    document_type: Optional[Literal["id_card", "passport", "school_id", "other"]] = None
    status: Optional[Literal["pending", "approved", "rejected"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class VerificationStatus(BaseModel):
    """Model for verification status"""
    is_verified: bool
    verification_level: Literal["none", "basic", "full"] = "none"
    documents_submitted: int = 0
    documents_approved: int = 0 