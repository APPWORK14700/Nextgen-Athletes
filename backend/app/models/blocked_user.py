from typing import Optional
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class BlockedUser(BaseModelWithID):
    """Blocked user model for user blocking functionality"""
    user_id: str
    blocked_user_id: str
    reason: Optional[str] = None


class BlockedUserCreate(BaseModel):
    """Model for creating blocked user"""
    blocked_user_id: str
    reason: Optional[str] = None 