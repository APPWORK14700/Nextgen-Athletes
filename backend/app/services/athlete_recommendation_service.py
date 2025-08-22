"""
Athlete Recommendation Service - Handles athlete recommendations for scouts
"""
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from .database_service import DatabaseService, DatabaseError
from .exceptions import AthleteServiceError, RecommendationError
from ..config.athlete_config import get_config
from ..utils.performance_monitor import performance_monitor
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class AthleteRecommendationService:
    """Service for providing athlete recommendations to scouts"""
    
    def __init__(self, environment: str = None):
        self.config = get_config(environment)
        
        # Validate required config sections
        required_sections = ['collections', 'recommendation_weights', 'experience_thresholds', 'field_weights']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        self.collections = self.config['collections']
        self.recommendation_weights = self.config['recommendation_weights']
        self.experience_thresholds = self.config['experience_thresholds']
        
        # Initialize repositories
        self.athlete_repository = DatabaseService(self.collections["athlete_profiles"])
        self.scout_prefs_repository = DatabaseService(self.collections["scout_preferences"])
    
    @performance_monitor.monitor("get_recommended_athletes")
    async def get_recommended_athletes(self, scout_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recommended athletes for a scout with improved algorithm"""
        try:
            # Validate inputs
            if not scout_id or not isinstance(scout_id, str):
                raise ValueError("scout_id must be a non-empty string")
            
            if not isinstance(limit, int) or limit <= 0:
                limit = 20
                logger.warning(f"Invalid limit provided, using default: {limit}")
            
            # Get scout preferences if available
            scout_preferences = await self._get_scout_preferences(scout_id)
            
            # Build base filters for active athletes
            base_filters = [FieldFilter("is_active", "==", True)]
            
            # Apply scout preferences if available
            if scout_preferences:
                base_filters = self._apply_scout_preferences(base_filters, scout_preferences)
            
            # Get athletes with optimized filtering
            athletes = await self._get_athletes_with_optimized_filtering(base_filters, limit * 2)
            
            if not athletes:
                logger.info(f"No athletes found for scout {scout_id} with given filters")
                return []
            
            # Score and rank athletes
            scored_athletes = await self._score_athletes_for_scout(athletes, scout_preferences)
            
            if not scored_athletes:
                logger.warning(f"No athletes scored for scout {scout_id}")
                return []
            
            # Sort by score and return top results
            scored_athletes.sort(key=lambda x: x["score"], reverse=True)
            
            # Remove score from final results
            for athlete in scored_athletes[:limit]:
                athlete.pop("score", None)
            
            logger.info(f"Returning {len(scored_athletes[:limit])} recommended athletes for scout {scout_id}")
            return scored_athletes[:limit]
            
        except DatabaseError as e:
            logger.error(f"Database error getting recommended athletes for scout {scout_id}: {e}")
            raise
        except ValueError as e:
            logger.error(f"Validation error for scout {scout_id}: {e}")
            raise RecommendationError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting recommended athletes for scout {scout_id}: {e}")
            raise RecommendationError(f"Failed to get recommended athletes: {str(e)}")
    
    @performance_monitor.monitor("get_athletes_by_preferences")
    async def get_athletes_by_preferences(self, preferences: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """Get athletes based on specific preferences without requiring scout ID"""
        try:
            # Validate inputs
            if not self._validate_preferences(preferences):
                raise ValueError("Invalid preferences format")
            
            if not isinstance(limit, int) or limit <= 0:
                limit = 20
                logger.warning(f"Invalid limit provided, using default: {limit}")
            
            # Build filters based on preferences
            base_filters = [FieldFilter("is_active", "==", True)]
            base_filters = self._apply_scout_preferences(base_filters, preferences)
            
            # Get athletes with optimized filtering
            athletes = await self._get_athletes_with_optimized_filtering(base_filters, limit * 2)
            
            if not athletes:
                logger.info("No athletes found with given preferences")
                return []
            
            # Score athletes based on preferences
            scored_athletes = await self._score_athletes_for_scout(athletes, preferences)
            
            if not scored_athletes:
                logger.warning("No athletes scored with given preferences")
                return []
            
            # Sort by score and return top results
            scored_athletes.sort(key=lambda x: x["score"], reverse=True)
            
            # Remove score from final results
            for athlete in scored_athletes[:limit]:
                athlete.pop("score", None)
            
            logger.info(f"Returning {len(scored_athletes[:limit])} athletes by preferences")
            return scored_athletes[:limit]
            
        except ValueError as e:
            logger.error(f"Validation error in preferences: {e}")
            raise RecommendationError(f"Invalid preferences: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting athletes by preferences: {e}")
            raise RecommendationError(f"Failed to get athletes by preferences: {str(e)}")
    
    @performance_monitor.monitor("get_similar_athletes")
    async def get_similar_athletes(self, athlete_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get athletes similar to a given athlete"""
        try:
            # Validate inputs
            if not athlete_id or not isinstance(athlete_id, str):
                raise ValueError("athlete_id must be a non-empty string")
            
            if not isinstance(limit, int) or limit <= 0:
                limit = 10
                logger.warning(f"Invalid limit provided, using default: {limit}")
            
            # Get the reference athlete
            reference_athlete = await self.athlete_repository.get_by_field("user_id", athlete_id)
            if not reference_athlete:
                raise RecommendationError(f"Athlete {athlete_id} not found")
            
            # Build filters based on reference athlete characteristics
            base_filters = [FieldFilter("is_active", "==", True)]
            
            # Add sport category filter
            if reference_athlete.get("primary_sport_category_id"):
                base_filters.append(FieldFilter("primary_sport_category_id", "==", reference_athlete["primary_sport_category_id"]))
            
            # Add position filter if available
            if reference_athlete.get("position"):
                base_filters.append(FieldFilter("position", "==", reference_athlete["position"]))
            
            # Add location filter if available
            if reference_athlete.get("location"):
                base_filters.append(FieldFilter("location", "==", reference_athlete["location"]))
            
            # Exclude the reference athlete
            base_filters.append(FieldFilter("user_id", "!=", athlete_id))
            
            # Get athletes with optimized filtering
            athletes = await self._get_athletes_with_optimized_filtering(base_filters, limit * 2)
            
            if not athletes:
                logger.info(f"No similar athletes found for {athlete_id}")
                return []
            
            # Score athletes based on similarity to reference athlete
            scored_athletes = await self._score_athletes_for_similarity(athletes, reference_athlete)
            
            if not scored_athletes:
                logger.warning(f"No athletes scored for similarity to {athlete_id}")
                return []
            
            # Sort by score and return top results
            scored_athletes.sort(key=lambda x: x["score"], reverse=True)
            
            # Remove score from final results
            for athlete in scored_athletes[:limit]:
                athlete.pop("score", None)
            
            logger.info(f"Returning {len(scored_athletes[:limit])} similar athletes for {athlete_id}")
            return scored_athletes[:limit]
            
        except ValueError as e:
            logger.error(f"Validation error for athlete {athlete_id}: {e}")
            raise RecommendationError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Error getting similar athletes for {athlete_id}: {e}")
            raise RecommendationError(f"Failed to get similar athletes: {str(e)}")
    
    # Private helper methods
    
    async def _get_scout_preferences(self, scout_id: str) -> Optional[Dict[str, Any]]:
        """Get scout preferences for recommendations"""
        try:
            preferences = await self.scout_prefs_repository.get_by_field("scout_id", scout_id)
            
            if preferences:
                return {
                    "sport_category_ids": preferences.get("sport_category_ids", []),
                    "location": preferences.get("location"),
                    "min_age": preferences.get("min_age"),
                    "max_age": preferences.get("max_age"),
                    "position_focus": preferences.get("position_focus", []),
                    "experience_level": preferences.get("experience_level")
                }
            
            return None
            
        except DatabaseError as e:
            logger.warning(f"Database error getting scout preferences for {scout_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting scout preferences for {scout_id}: {e}")
            return None
    
    def _validate_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Validate scout preferences"""
        if not preferences:
            return True
        
        # Check for required field types
        if 'sport_category_ids' in preferences and preferences['sport_category_ids'] is not None:
            if not isinstance(preferences['sport_category_ids'], list):
                return False
        
        if 'position_focus' in preferences and preferences['position_focus'] is not None:
            if not isinstance(preferences['position_focus'], list):
                return False
        
        if 'min_age' in preferences and preferences['min_age'] is not None:
            if not isinstance(preferences['min_age'], int) or preferences['min_age'] < 0:
                return False
        
        if 'max_age' in preferences and preferences['max_age'] is not None:
            if not isinstance(preferences['max_age'], int) or preferences['max_age'] < 0:
                return False
        
        # Validate age range if both are provided
        if (preferences.get('min_age') is not None and 
            preferences.get('max_age') is not None and
            preferences['min_age'] > preferences['max_age']):
            return False
        
        return True
    
    def _apply_scout_preferences(self, base_filters: List[FieldFilter], preferences: Dict[str, Any]) -> List[FieldFilter]:
        """Apply scout preferences to base filters"""
        if preferences.get("sport_category_ids"):
            # Use 'in' operator for multiple sport categories
            base_filters.append(FieldFilter("primary_sport_category_id", "in", preferences["sport_category_ids"]))
        
        if preferences.get("location"):
            base_filters.append(FieldFilter("location", "==", preferences["location"]))
        
        if preferences.get("min_age") or preferences.get("max_age"):
            today = date.today()
            if preferences.get("max_age"):
                min_date = today - relativedelta(years=preferences["max_age"])
                base_filters.append(FieldFilter("date_of_birth", ">=", min_date.isoformat()))
            if preferences.get("min_age"):
                max_date = today - relativedelta(years=preferences["min_age"])
                base_filters.append(FieldFilter("date_of_birth", "<=", max_date.isoformat()))
        
        return base_filters
    
    async def _get_athletes_with_optimized_filtering(self, base_filters: List[FieldFilter], limit: int):
        """Get athletes with optimized filtering and pagination"""
        athletes = await self.athlete_repository.query(base_filters, limit)
        
        # Validate that we got athletes and they have required fields
        if athletes and not all('user_id' in athlete for athlete in athletes):
            logger.warning("Some athletes missing required user_id field")
            athletes = [a for a in athletes if 'user_id' in a]
        
        return athletes
    
    async def _score_athletes_for_scout(self, athletes: List[Dict[str, Any]], scout_preferences: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score athletes based on scout preferences and profile completeness"""
        scored_athletes = []
        
        for athlete in athletes:
            score = 0
            
            # Base score from profile completion
            profile_completion = self._calculate_completion_percentage(athlete)
            score += profile_completion * self.recommendation_weights['profile_completion']
            
            # Sport category match
            if scout_preferences and scout_preferences.get("sport_category_ids"):
                if athlete.get("primary_sport_category_id") in scout_preferences["sport_category_ids"]:
                    score += self.recommendation_weights['sport_category_match']
            
            # Position focus match
            if scout_preferences and scout_preferences.get("position_focus"):
                if athlete.get("position") in scout_preferences["position_focus"]:
                    score += self.recommendation_weights['position_match']
            
            # Location match
            if scout_preferences and scout_preferences.get("location"):
                if athlete.get("location") == scout_preferences["location"]:
                    score += self.recommendation_weights['location_match']
            
            # Experience level consideration
            if scout_preferences and scout_preferences.get("experience_level"):
                experience_score = self._calculate_experience_score(athlete, scout_preferences["experience_level"])
                score += experience_score
            
            # Recent activity bonus (if athlete has recent updates)
            if athlete.get("updated_at"):
                try:
                    last_updated = datetime.fromisoformat(athlete["updated_at"])
                    days_since_update = (datetime.now(timezone.utc) - last_updated).days
                    if days_since_update <= self.recommendation_weights['recent_activity_days']:
                        score += self.recommendation_weights['recent_activity_bonus']
                except (ValueError, TypeError) as e:
                    logger.debug(f"Date parsing error for athlete {athlete.get('user_id', 'unknown')}: {e}")
            
            # Add score to athlete data
            athlete_copy = athlete.copy()
            athlete_copy["score"] = score
            scored_athletes.append(athlete_copy)
        
        return scored_athletes
    
    async def _score_athletes_for_similarity(self, athletes: List[Dict[str, Any]], reference_athlete: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Score athletes based on similarity to reference athlete"""
        scored_athletes = []
        
        for athlete in athletes:
            score = 0
            
            # Sport category match - use config weights
            if (athlete.get("primary_sport_category_id") == 
                reference_athlete.get("primary_sport_category_id")):
                score += self.recommendation_weights['sport_category_match']
            
            # Position match
            if (athlete.get("position") == 
                reference_athlete.get("position")):
                score += self.recommendation_weights['position_match']
            
            # Location match
            if (athlete.get("location") == 
                reference_athlete.get("location")):
                score += self.recommendation_weights['location_match']
            
            # Age similarity using config weights
            if athlete.get("date_of_birth") and reference_athlete.get("date_of_birth"):
                try:
                    athlete_age = self._calculate_age(athlete["date_of_birth"])
                    reference_age = self._calculate_age(reference_athlete["date_of_birth"])
                    age_diff = abs(athlete_age - reference_age)
                    
                    if age_diff <= 3:
                        score += self.recommendation_weights.get('age_similarity_close', 25)
                    elif age_diff <= 5:
                        score += self.recommendation_weights.get('age_similarity_medium', 15)
                    elif age_diff <= 10:
                        score += self.recommendation_weights.get('age_similarity_far', 5)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Age calculation error for athlete {athlete.get('user_id', 'unknown')}: {e}")
            
            # Profile completion similarity using config weights
            athlete_completion = self._calculate_completion_percentage(athlete)
            reference_completion = self._calculate_completion_percentage(reference_athlete)
            completion_diff = abs(athlete_completion - reference_completion)
            
            if completion_diff <= 10:
                score += self.recommendation_weights.get('completion_similarity_close', 20)
            elif completion_diff <= 20:
                score += self.recommendation_weights.get('completion_similarity_medium', 10)
            
            # Add score to athlete data
            athlete_copy = athlete.copy()
            athlete_copy["score"] = score
            scored_athletes.append(athlete_copy)
        
        return scored_athletes
    
    def _calculate_experience_score(self, athlete: Dict[str, Any], target_experience: str) -> int:
        """Calculate experience score based on career highlights and age"""
        score = 0
        
        # Career highlights length (simple proxy for experience)
        career_highlights = athlete.get("career_highlights", "")
        if career_highlights:
            highlight_length = len(career_highlights)
            if highlight_length > self.experience_thresholds['extensive_experience']:
                score += self.experience_thresholds['extensive_score']
            elif highlight_length > self.experience_thresholds['moderate_experience']:
                score += self.experience_thresholds['moderate_score']
            elif highlight_length > self.experience_thresholds['min_experience']:
                score += self.experience_thresholds['min_score']
        
        # Age-based experience (if date_of_birth is available)
        if athlete.get("date_of_birth"):
            try:
                age = self._calculate_age(athlete["date_of_birth"])
                
                if target_experience == "junior" and age <= 18:
                    score += self.experience_thresholds['age_bonus']
                elif target_experience == "intermediate" and 19 <= age <= 22:
                    score += self.experience_thresholds['age_bonus']
                elif target_experience == "senior" and age >= 23:
                    score += self.experience_thresholds['age_bonus']
                    
            except (ValueError, TypeError) as e:
                logger.debug(f"Age calculation error for athlete {athlete.get('user_id', 'unknown')}: {e}")
        
        return score
    
    def _calculate_completion_percentage(self, profile_doc: Dict[str, Any]) -> int:
        """Calculate profile completion percentage"""
        field_weights = self.config['field_weights']
        total_weight = sum(field_weights.values())
        
        if total_weight == 0:
            logger.warning("Field weights configuration is empty or invalid")
            return 0
        
        filled_weight = sum(
            field_weights[field] for field, value in profile_doc.items() 
            if field in field_weights and value is not None and value != ""
        )
        
        return int((filled_weight / total_weight) * 100)
    
    def _calculate_age(self, date_of_birth: str) -> int:
        """Calculate age from date of birth string"""
        if not date_of_birth:
            return 0
            
        try:
            birth_date = datetime.fromisoformat(date_of_birth).date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return max(0, age)  # Ensure non-negative age
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid date format for {date_of_birth}: {e}")
            return 0 