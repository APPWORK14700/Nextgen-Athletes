from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Achievement(BaseModel):
    """Achievement model"""
    type: str
    title: str
    description: str
    date_achieved: date
    evidence_url: Optional[str] = None


class StatsAchievements(BaseModelWithID):
    """Stats and achievements model for athletes"""
    athlete_id: str
    sport_category_id: str
    season: str
    team_name: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    stats: Dict[str, Any] = {}  # Dynamic based on sport category
    achievements: List[Achievement] = []


class StatsAchievementsCreate(BaseModel):
    """Model for creating stats and achievements"""
    sport_category_id: str
    season: str
    team_name: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    stats: Dict[str, Any] = {}
    achievements: Optional[List[Achievement]] = []


class StatsAchievementsUpdate(BaseModel):
    """Model for updating stats and achievements"""
    season: Optional[str] = None
    team_name: Optional[str] = None
    league: Optional[str] = None
    position: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    achievements: Optional[List[Achievement]] = None


class AchievementCreate(BaseModel):
    """Model for creating achievement"""
    type: str
    title: str
    description: str
    date_achieved: date
    evidence_url: Optional[str] = None 