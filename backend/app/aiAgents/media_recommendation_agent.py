"""
AI Agent for handling media recommendation operations
"""
import logging
import random
from typing import Dict, Any, List

from ..services.database_service import DatabaseService
from ..services.ai_service import AIService
from ..config.media_config import get_media_config
from ..api.exceptions import ValidationError, DatabaseError
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class MediaRecommendationAgent:
    """AI Agent responsible for providing media recommendations"""
    
    def __init__(self):
        self.database_service = DatabaseService("media")
        self.ai_service = AIService()  # For AI-powered scoring
        self.config = get_media_config()
    
    async def get_recommended_reels(self, scout_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recommended reels for scout"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required")
            
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Get all reels with approved moderation status
            filters = [
                FieldFilter("type", "==", "reel"),
                FieldFilter("moderation_status", "==", "approved")
            ]
            
            reels = await self.database_service.query(filters, limit * 2)  # Get more to filter
            
            # Score and rank reels based on AI analysis and scout preferences
            scored_reels = await self._score_media_for_scout(reels, scout_id)
            
            # Return top scored reels
            return scored_reels[:limit]
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting recommended reels for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to get recommended reels: {str(e)}")
    
    async def get_recommended_media_by_sport(self, sport_category: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recommended media by sport category"""
        try:
            if not sport_category:
                raise ValidationError("Sport category is required")
            
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Get media with completed AI analysis for specific sport
            filters = [
                FieldFilter("moderation_status", "==", "approved"),
                FieldFilter("ai_analysis.status", "==", "completed")
            ]
            
            media = await self.database_service.query(filters, limit * 2)
            
            # Filter by sport category if available
            if sport_category != "all":
                # This is a placeholder - implement based on your data structure
                media = [m for m in media if m.get("sport_category") == sport_category]
            
            # Score media based on AI analysis quality
            scored_media = await self._score_media_by_ai_quality(media)
            
            return scored_media[:limit]
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting recommended media by sport {sport_category}: {e}")
            raise DatabaseError(f"Failed to get recommended media: {str(e)}")
    
    async def get_trending_media(self, limit: int = 20, time_window_hours: int = 24) -> List[Dict[str, Any]]:
        """Get trending media based on recent activity"""
        try:
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            if time_window_hours < 1 or time_window_hours > 168:  # Max 1 week
                raise ValidationError("Time window must be between 1 and 168 hours")
            
            # Get recent media with completed AI analysis
            filters = [
                FieldFilter("moderation_status", "==", "approved"),
                FieldFilter("ai_analysis.status", "==", "completed")
            ]
            
            media = await self.database_service.query(filters, limit * 2)
            
            # Score media based on AI rating and recency
            scored_media = await self._score_media_for_trending(media, time_window_hours)
            
            return scored_media[:limit]
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting trending media: {e}")
            raise DatabaseError(f"Failed to get trending media: {str(e)}")
    
    async def get_personalized_recommendations(self, user_id: str, user_preferences: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """Get personalized media recommendations based on user preferences"""
        try:
            if not user_id:
                raise ValidationError("User ID is required")
            
            if not user_preferences:
                raise ValidationError("User preferences are required")
            
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # Get approved media with completed AI analysis
            filters = [
                FieldFilter("moderation_status", "==", "approved"),
                FieldFilter("ai_analysis.status", "==", "completed")
            ]
            
            media = await self.database_service.query(filters, limit * 2)
            
            # Score media based on user preferences and AI analysis
            scored_media = await self._score_media_for_user(media, user_preferences)
            
            return scored_media[:limit]
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting personalized recommendations for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get personalized recommendations: {str(e)}")
    
    async def get_ai_powered_recommendations(self, user_preferences: Dict[str, Any], available_media: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
        """Get AI-powered recommendations based on user preferences and media analysis"""
        try:
            if not available_media:
                return []
            
            scored_media = []
            
            for media in available_media:
                score = 0
                
                # Score based on AI rating
                ai_analysis = media.get("ai_analysis", {})
                rating = ai_analysis.get("rating")
                
                if rating == "exceptional":
                    score += 100
                elif rating == "excellent":
                    score += 80
                elif rating == "good":
                    score += 60
                elif rating == "developing":
                    score += 40
                else:
                    score += 20
                
                # Score based on user preferences
                if user_preferences.get("sport_category_id") == media.get("sport_category_id"):
                    score += 30
                
                if user_preferences.get("location") and media.get("location") == user_preferences["location"]:
                    score += 20
                
                # Score based on AI confidence
                confidence = ai_analysis.get("confidence_score", 0.7)
                score += int(confidence * 20)
                
                # Score based on media quality
                if media.get("type") == "video":
                    score += 10
                elif media.get("type") == "reel":
                    score += 15
                
                # Add some randomness to avoid always showing the same results
                score += random.uniform(-10, 10)
                
                scored_media.append({
                    "media": media,
                    "score": score
                })
            
            # Sort by score and return top results
            scored_media.sort(key=lambda x: x["score"], reverse=True)
            
            return [item["media"] for item in scored_media[:limit]]
            
        except Exception as e:
            logger.error(f"Error getting AI-powered recommendations: {e}")
            raise
    
    async def _score_media_for_scout(self, media_list: List[Dict[str, Any]], scout_id: str) -> List[Dict[str, Any]]:
        """Score media specifically for a scout's preferences"""
        try:
            # TODO: Get scout preferences from database
            # For now, use generic scoring
            return await self._score_media_by_ai_quality(media_list)
        except Exception as e:
            logger.error(f"Error scoring media for scout {scout_id}: {e}")
            return media_list
    
    async def _score_media_by_ai_quality(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score media based on AI analysis quality"""
        try:
            scored_media = []
            
            for media in media_list:
                score = 0
                ai_analysis = media.get("ai_analysis", {})
                
                # Score based on rating
                rating = ai_analysis.get("rating")
                if rating == "exceptional":
                    score += 100
                elif rating == "excellent":
                    score += 80
                elif rating == "good":
                    score += 60
                elif rating == "developing":
                    score += 40
                else:
                    score += 20
                
                # Score based on confidence
                confidence = ai_analysis.get("confidence_score", 0.7)
                score += int(confidence * 30)
                
                # Score based on completeness of analysis
                if ai_analysis.get("detailed_analysis"):
                    score += 20
                if ai_analysis.get("sport_specific_metrics"):
                    score += 15
                
                scored_media.append({
                    "media": media,
                    "score": score
                })
            
            # Sort by score
            scored_media.sort(key=lambda x: x["score"], reverse=True)
            return [item["media"] for item in scored_media]
            
        except Exception as e:
            logger.error(f"Error scoring media by AI quality: {e}")
            return media_list
    
    async def _score_media_for_trending(self, media_list: List[Dict[str, Any]], time_window_hours: int) -> List[Dict[str, Any]]:
        """Score media for trending based on AI rating and recency"""
        try:
            scored_media = []
            
            for media in media_list:
                score = 0
                ai_analysis = media.get("ai_analysis", {})
                
                # Base score from AI rating
                rating = ai_analysis.get("rating")
                if rating == "exceptional":
                    score += 100
                elif rating == "excellent":
                    score += 80
                elif rating == "good":
                    score += 60
                elif rating == "developing":
                    score += 40
                else:
                    score += 20
                
                # Bonus for high confidence
                confidence = ai_analysis.get("confidence_score", 0.7)
                if confidence > 0.9:
                    score += 25
                elif confidence > 0.8:
                    score += 15
                
                # Bonus for recent uploads (placeholder for actual timestamp logic)
                # TODO: Implement actual timestamp-based scoring
                
                scored_media.append({
                    "media": media,
                    "score": score
                })
            
            # Sort by score
            scored_media.sort(key=lambda x: x["score"], reverse=True)
            return [item["media"] for item in scored_media]
            
        except Exception as e:
            logger.error(f"Error scoring media for trending: {e}")
            return media_list
    
    async def _score_media_for_user(self, media_list: List[Dict[str, Any]], user_preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Score media based on user preferences and AI analysis"""
        try:
            scored_media = []
            
            for media in media_list:
                score = 0
                ai_analysis = media.get("ai_analysis", {})
                
                # Base AI score
                rating = ai_analysis.get("rating")
                if rating == "exceptional":
                    score += 100
                elif rating == "excellent":
                    score += 80
                elif rating == "good":
                    score += 60
                elif rating == "developing":
                    score += 40
                else:
                    score += 20
                
                # Preference matching
                if user_preferences.get("sport_category") == media.get("sport_category"):
                    score += 30
                
                if user_preferences.get("min_rating"):
                    min_rating_score = self._rating_to_score(user_preferences["min_rating"])
                    if score >= min_rating_score:
                        score += 20
                
                # Location preference
                if user_preferences.get("location") and media.get("location") == user_preferences["location"]:
                    score += 20
                
                # Media type preference
                preferred_type = user_preferences.get("preferred_media_type")
                if preferred_type and media.get("type") == preferred_type:
                    score += 15
                
                scored_media.append({
                    "media": media,
                    "score": score
                })
            
            # Sort by score
            scored_media.sort(key=lambda x: x["score"], reverse=True)
            return [item["media"] for item in scored_media]
            
        except Exception as e:
            logger.error(f"Error scoring media for user: {e}")
            return media_list
    
    def _rating_to_score(self, rating: str) -> int:
        """Convert rating string to numeric score"""
        rating_scores = {
            "exceptional": 100,
            "excellent": 80,
            "good": 60,
            "developing": 40,
            "needs_improvement": 20
        }
        return rating_scores.get(rating.lower(), 0) 