from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

from ..models.athlete import AthleteProfile, AthleteProfileCreate, AthleteProfileUpdate, AthleteSearchFilters, AthleteAnalytics
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class AthleteService:
    """Athlete service for managing athlete profiles and related operations"""
    
    def __init__(self):
        self.athlete_service = DatabaseService("athlete_profiles")
        self.user_service = DatabaseService("users")
        self.media_service = DatabaseService("media")
        self.stats_service = DatabaseService("stats_achievements")
    
    async def create_athlete_profile(self, user_id: str, profile_data: AthleteProfileCreate) -> Dict[str, Any]:
        """Create athlete profile"""
        try:
            # Check if profile already exists
            existing_profile = await self.athlete_service.get_by_field("user_id", user_id)
            if existing_profile:
                raise ValueError("Athlete profile already exists")
            
            # Create athlete profile
            profile_doc = {
                "user_id": user_id,
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "date_of_birth": profile_data.date_of_birth.isoformat(),
                "gender": profile_data.gender,
                "location": profile_data.location,
                "primary_sport_category_id": profile_data.primary_sport_category_id,
                "secondary_sport_category_ids": profile_data.secondary_sport_category_ids or [],
                "position": profile_data.position,
                "height_cm": profile_data.height_cm,
                "weight_kg": profile_data.weight_kg,
                "academic_info": profile_data.academic_info,
                "career_highlights": profile_data.career_highlights
            }
            
            profile_id = await self.athlete_service.create(profile_doc)
            
            # Update user profile completion
            await self._update_profile_completion(user_id)
            
            return await self.get_athlete_profile(user_id)
            
        except Exception as e:
            logger.error(f"Error creating athlete profile for user {user_id}: {e}")
            raise
    
    async def get_athlete_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get athlete profile by user ID"""
        try:
            profile_doc = await self.athlete_service.get_by_field("user_id", user_id)
            if not profile_doc:
                return None
            
            # Convert date string back to date object
            if "date_of_birth" in profile_doc:
                profile_doc["date_of_birth"] = datetime.fromisoformat(profile_doc["date_of_birth"]).date()
            
            return profile_doc
            
        except Exception as e:
            logger.error(f"Error getting athlete profile for user {user_id}: {e}")
            raise
    
    async def update_athlete_profile(self, user_id: str, profile_data: AthleteProfileUpdate) -> Dict[str, Any]:
        """Update athlete profile"""
        try:
            update_data = {}
            
            if profile_data.first_name is not None:
                update_data["first_name"] = profile_data.first_name
            if profile_data.last_name is not None:
                update_data["last_name"] = profile_data.last_name
            if profile_data.date_of_birth is not None:
                update_data["date_of_birth"] = profile_data.date_of_birth.isoformat()
            if profile_data.gender is not None:
                update_data["gender"] = profile_data.gender
            if profile_data.location is not None:
                update_data["location"] = profile_data.location
            if profile_data.primary_sport_category_id is not None:
                update_data["primary_sport_category_id"] = profile_data.primary_sport_category_id
            if profile_data.secondary_sport_category_ids is not None:
                update_data["secondary_sport_category_ids"] = profile_data.secondary_sport_category_ids
            if profile_data.position is not None:
                update_data["position"] = profile_data.position
            if profile_data.height_cm is not None:
                update_data["height_cm"] = profile_data.height_cm
            if profile_data.weight_kg is not None:
                update_data["weight_kg"] = profile_data.weight_kg
            if profile_data.academic_info is not None:
                update_data["academic_info"] = profile_data.academic_info
            if profile_data.career_highlights is not None:
                update_data["career_highlights"] = profile_data.career_highlights
            if profile_data.profile_image_url is not None:
                update_data["profile_image_url"] = profile_data.profile_image_url
            
            if update_data:
                # Find the profile document ID
                profile_doc = await self.athlete_service.get_by_field("user_id", user_id)
                if not profile_doc:
                    raise ValueError("Athlete profile not found")
                
                await self.athlete_service.update(profile_doc["id"], update_data)
                
                # Update profile completion
                await self._update_profile_completion(user_id)
            
            return await self.get_athlete_profile(user_id)
            
        except Exception as e:
            logger.error(f"Error updating athlete profile for user {user_id}: {e}")
            raise
    
    async def search_athletes(self, filters: AthleteSearchFilters) -> PaginatedResponse:
        """Search athletes with filters"""
        try:
            firestore_filters = []
            
            if filters.sport_category_id:
                firestore_filters.append(FieldFilter("primary_sport_category_id", "==", filters.sport_category_id))
            
            if filters.position:
                firestore_filters.append(FieldFilter("position", "==", filters.position))
            
            if filters.gender:
                firestore_filters.append(FieldFilter("gender", "==", filters.gender))
            
            if filters.location:
                firestore_filters.append(FieldFilter("location", "==", filters.location))
            
            # Get athletes with basic filters
            athletes = await self.athlete_service.query(firestore_filters, filters.limit, filters.offset)
            
            # Apply age filters in memory (since Firestore doesn't support date range queries easily)
            if filters.min_age or filters.max_age:
                filtered_athletes = []
                today = date.today()
                
                for athlete in athletes:
                    if "date_of_birth" in athlete:
                        dob = datetime.fromisoformat(athlete["date_of_birth"]).date()
                        age = relativedelta(today, dob).years
                        
                        if filters.min_age and age < filters.min_age:
                            continue
                        if filters.max_age and age > filters.max_age:
                            continue
                        
                        filtered_athletes.append(athlete)
                
                athletes = filtered_athletes
            
            # Apply rating filter (this would require joining with media data)
            if filters.min_rating:
                # This is a simplified implementation
                # In production, you'd want to join with media data to get AI ratings
                pass
            
            # Get total count
            total_count = await self.athlete_service.count(firestore_filters)
            
            return PaginatedResponse(
                count=total_count,
                results=athletes,
                next=f"?limit={filters.limit}&offset={filters.offset + filters.limit}" if filters.offset + filters.limit < total_count else None,
                previous=f"?limit={filters.limit}&offset={max(0, filters.offset - filters.limit)}" if filters.offset > 0 else None
            )
            
        except Exception as e:
            logger.error(f"Error searching athletes: {e}")
            raise
    
    async def get_athlete_media(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get athlete's media"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            media = await self.media_service.query(filters)
            return media
            
        except Exception as e:
            logger.error(f"Error getting athlete media for {athlete_id}: {e}")
            raise
    
    async def get_athlete_stats(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get athlete's stats and achievements"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            stats = await self.stats_service.query(filters)
            return stats
            
        except Exception as e:
            logger.error(f"Error getting athlete stats for {athlete_id}: {e}")
            raise
    
    async def get_athlete_analytics(self, athlete_id: str) -> AthleteAnalytics:
        """Get athlete analytics"""
        try:
            # This would typically aggregate data from various collections
            # For now, return basic counts
            
            # Count media
            media_filters = [FieldFilter("athlete_id", "==", athlete_id)]
            media_count = await self.media_service.count(media_filters)
            
            # Count stats
            stats_filters = [FieldFilter("athlete_id", "==", athlete_id)]
            stats_count = await self.stats_service.count(stats_filters)
            
            return AthleteAnalytics(
                profile_views=0,  # Would need to track this
                media_views=media_count,
                messages_received=0,  # Would need to track this
                opportunities_applied=0,  # Would need to track this
                applications_accepted=0  # Would need to track this
            )
            
        except Exception as e:
            logger.error(f"Error getting athlete analytics for {athlete_id}: {e}")
            raise
    
    async def get_recommended_athletes(self, scout_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recommended athletes for a scout"""
        try:
            # This is a simplified recommendation algorithm
            # In production, you'd want to implement a more sophisticated recommendation system
            
            # Get all active athletes
            filters = [FieldFilter("is_active", "==", True)]
            athletes = await self.athlete_service.query(filters, limit)
            
            # For now, just return random athletes
            # In production, you'd want to consider:
            # - Scout's focus areas
            # - Athlete ratings
            # - Location preferences
            # - Sport category preferences
            
            return athletes
            
        except Exception as e:
            logger.error(f"Error getting recommended athletes for scout {scout_id}: {e}")
            raise
    
    async def _update_profile_completion(self, user_id: str) -> None:
        """Update athlete profile completion percentage"""
        try:
            profile_doc = await self.athlete_service.get_by_field("user_id", user_id)
            if not profile_doc:
                return
            
            # Calculate completion percentage based on filled fields
            required_fields = [
                "first_name", "last_name", "date_of_birth", "gender", 
                "location", "primary_sport_category_id", "position", 
                "height_cm", "weight_kg"
            ]
            
            optional_fields = [
                "academic_info", "career_highlights", "profile_image_url",
                "secondary_sport_category_ids"
            ]
            
            filled_required = sum(1 for field in required_fields if profile_doc.get(field))
            filled_optional = sum(1 for field in optional_fields if profile_doc.get(field))
            
            total_fields = len(required_fields) + len(optional_fields)
            filled_fields = filled_required + filled_optional
            
            completion_percentage = int((filled_fields / total_fields) * 100)
            
            # Update user profile completion
            user_profile_service = DatabaseService("user_profiles")
            await user_profile_service.update(user_id, {"profile_completion": completion_percentage})
            
        except Exception as e:
            logger.error(f"Error updating profile completion for user {user_id}: {e}")
            raise
    
    async def get_athlete_by_id(self, athlete_id: str) -> Optional[Dict[str, Any]]:
        """Get athlete profile by athlete ID (user ID)"""
        try:
            return await self.get_athlete_profile(athlete_id)
            
        except Exception as e:
            logger.error(f"Error getting athlete by ID {athlete_id}: {e}")
            raise
    
    async def delete_athlete_profile(self, user_id: str) -> bool:
        """Delete athlete profile"""
        try:
            profile_doc = await self.athlete_service.get_by_field("user_id", user_id)
            if not profile_doc:
                return False
            
            await self.athlete_service.delete(profile_doc["id"])
            return True
            
        except Exception as e:
            logger.error(f"Error deleting athlete profile for user {user_id}: {e}")
            raise 