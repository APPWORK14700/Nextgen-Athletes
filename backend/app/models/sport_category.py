from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Validation(BaseModel):
    """Validation rules for stats fields"""
    min: Optional[float] = None
    max: Optional[float] = None
    pattern: Optional[str] = None


class StatsField(BaseModel):
    """Stats field definition for sport categories"""
    key: str
    label: str
    type: Literal["integer", "float", "string", "boolean"]
    unit: Optional[str] = None
    required: bool = False
    default_value: Optional[Any] = None
    validation: Optional[Validation] = None
    display_order: int


class AchievementType(BaseModel):
    """Achievement type definition for sport categories"""
    key: str
    label: str
    description: str
    icon_url: Optional[str] = None


class SportCategory(BaseModelWithID):
    """Sport category model with dynamic stats fields and achievement types"""
    name: str
    description: str
    icon_url: Optional[str] = None
    is_active: bool = True
    created_by: str
    stats_fields: List[StatsField] = []
    achievement_types: List[AchievementType] = []


class SportCategoryCreate(BaseModel):
    """Model for creating sport category"""
    name: str
    description: str
    icon_url: Optional[str] = None
    stats_fields: List[StatsField] = []
    achievement_types: List[AchievementType] = []


class SportCategoryUpdate(BaseModel):
    """Model for updating sport category"""
    name: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    is_active: Optional[bool] = None
    stats_fields: Optional[List[StatsField]] = None
    achievement_types: Optional[List[AchievementType]] = None


class SportCategorySearchFilters(BaseModel):
    """Model for sport category search filters"""
    is_active: Optional[bool] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class StatsTemplate(BaseModel):
    """Model for stats template response"""
    category: SportCategory
    stats_template: Dict[str, Any]
    achievement_types: List[AchievementType] 