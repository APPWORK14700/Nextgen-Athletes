from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class SearchHistory(BaseModelWithID):
    """Search history model for tracking user searches"""
    user_id: str
    search_type: Literal["athletes", "scouts", "opportunities"]
    query: str
    filters: Dict[str, Any] = {}


class SearchHistoryCreate(BaseModel):
    """Model for creating search history"""
    search_type: Literal["athletes", "scouts", "opportunities"]
    query: str
    filters: Optional[Dict[str, Any]] = None


class SearchHistorySearchFilters(BaseModel):
    """Model for search history filters"""
    search_type: Optional[Literal["athletes", "scouts", "opportunities"]] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0) 