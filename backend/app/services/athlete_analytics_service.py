"""
Athlete Analytics Service - Handles analytics, statistics, and bulk operations
"""
from typing import Optional, Dict, Any, List
import logging
import asyncio
from datetime import datetime, date, timezone
from dateutil.relativedelta import relativedelta
from functools import lru_cache

from ..models.athlete import AthleteAnalytics
from .database_service import DatabaseService, DatabaseError, ValidationError
from .exceptions import AthleteServiceError, StatisticsError, BulkOperationError
from ..config.athlete_config import get_config
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class AthleteAnalyticsService:
    """Service for athlete analytics, statistics, and bulk operations"""
    
    def __init__(self, environment: str = None):
        self.config = get_config(environment)
        self.collections = self.config['collections']
        self.bulk_limits = self.config['bulk_limits']
        self.statistics_limits = self.config['statistics_limits']
        self.performance_config = self.config['performance']
        
        # Initialize repositories
        self.athlete_repository = DatabaseService(self.collections["athlete_profiles"])
        self.media_repository = DatabaseService(self.collections["media"])
        self.stats_repository = DatabaseService(self.collections["stats_achievements"])
        self.profile_views_repository = DatabaseService(self.collections["profile_views"])
        self.messages_repository = DatabaseService(self.collections["messages"])
        self.applications_repository = DatabaseService(self.collections["opportunity_applications"])
    
    async def get_athlete_analytics(self, athlete_id: str) -> AthleteAnalytics:
        """Get athlete analytics with batch operations"""
        try:
            # Use batch operations to get multiple counts efficiently
            media_filters = [FieldFilter("athlete_id", "==", athlete_id)]
            stats_filters = [FieldFilter("athlete_id", "==", athlete_id)]
            
            # Execute queries in parallel
            media_count, stats_count = await asyncio.gather(
                self.media_repository.count(media_filters),
                self.stats_repository.count(stats_filters)
            )
            
            # Get additional analytics data
            profile_views = await self._get_profile_views(athlete_id)
            messages_received = await self._get_message_count(athlete_id)
            opportunities_applied = await self._get_opportunities_applied(athlete_id)
            applications_accepted = await self._get_applications_accepted(athlete_id)
            
            return AthleteAnalytics(
                profile_views=profile_views,
                media_views=media_count,
                messages_received=messages_received,
                opportunities_applied=opportunities_applied,
                applications_accepted=applications_accepted
            )
            
        except DatabaseError as e:
            logger.error(f"Database error getting athlete analytics for {athlete_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athlete analytics for {athlete_id}: {e}")
            raise StatisticsError(f"Failed to get athlete analytics: {str(e)}")
    
    async def get_athlete_statistics(self) -> Dict[str, Any]:
        """Get overall athlete statistics and demographics"""
        try:
            # Get total active athletes
            active_filters = [FieldFilter("is_active", "==", True)]
            total_active = await self.athlete_repository.count(active_filters)
            
            # Get total inactive athletes
            inactive_filters = [FieldFilter("is_active", "==", False)]
            total_inactive = await self.athlete_repository.count(inactive_filters)
            
            # Get athletes by gender
            male_filters = [FieldFilter("is_active", "==", True), FieldFilter("gender", "==", "male")]
            female_filters = [FieldFilter("is_active", "==", True), FieldFilter("gender", "==", "female")]
            
            male_count, female_count = await asyncio.gather(
                self.athlete_repository.count(male_filters),
                self.athlete_repository.count(female_filters)
            )
            
            # Get athletes by age groups
            age_stats = await self._get_age_group_statistics()
            
            # Get top sport categories
            sport_stats = await self._get_sport_category_statistics()
            
            # Get profile completion statistics
            completion_stats = await self._get_profile_completion_statistics()
            
            return {
                "total_athletes": total_active + total_inactive,
                "active_athletes": total_active,
                "inactive_athletes": total_inactive,
                "gender_distribution": {
                    "male": male_count,
                    "female": female_count,
                    "other": total_active - male_count - female_count
                },
                "age_distribution": age_stats,
                "sport_category_distribution": sport_stats,
                "profile_completion_distribution": completion_stats,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except DatabaseError as e:
            logger.error(f"Database error getting athlete statistics: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athlete statistics: {e}")
            raise StatisticsError(f"Failed to get athlete statistics: {str(e)}")
    
    async def bulk_update_athletes(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk update multiple athlete profiles with improved batch processing"""
        try:
            if not updates:
                raise BulkOperationError("No updates provided")
            
            if len(updates) > self.bulk_limits['max_bulk_update']:
                raise BulkOperationError(f"Cannot update more than {self.bulk_limits['max_bulk_update']} profiles at once")
            
            # Validate all updates before processing
            for update in updates:
                if not self._validate_update_data(update):
                    raise BulkOperationError(f"Invalid update data structure: {update}")
                
                # Validate user_id exists
                user_id = update.get("user_id")
                if not user_id:
                    raise BulkOperationError("Missing user_id in update data")
                
                # Check if athlete profile exists
                existing_profile = await self.athlete_repository.get_by_field("user_id", user_id)
                if not existing_profile:
                    raise BulkOperationError(f"Athlete profile not found for user {user_id}")
            
            results = {
                "successful": 0,
                "failed": 0,
                "errors": [],
                "total_processed": len(updates)
            }
            
            # Process updates in batches for better performance
            batch_size = self.bulk_limits['batch_size']
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                
                # Process batch concurrently
                batch_tasks = []
                for update in batch:
                    user_id = update.get("user_id")
                    update_data = update.get("data", {})
                    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    
                    # Create update task
                    task = self._update_single_athlete(user_id, update_data)
                    batch_tasks.append(task)
                
                # Execute batch concurrently
                try:
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    # Process batch results
                    for j, result in enumerate(batch_results):
                        if isinstance(result, Exception):
                            results["failed"] += 1
                            user_id = batch[j].get("user_id", "unknown")
                            results["errors"].append(f"Error updating user {user_id}: {str(result)}")
                        else:
                            results["successful"] += 1
                            
                except Exception as e:
                    # If batch fails, process individually
                    logger.warning(f"Batch processing failed, falling back to individual updates: {e}")
                    for update in batch:
                        try:
                            user_id = update.get("user_id")
                            update_data = update.get("data", {})
                            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
                            
                            await self.athlete_repository.update_by_field("user_id", user_id, update_data)
                            results["successful"] += 1
                                
                        except Exception as e:
                            results["failed"] += 1
                            results["errors"].append(f"Error updating user {update.get('user_id', 'unknown')}: {str(e)}")
            
            return results
            
        except BulkOperationError as e:
            logger.error(f"Bulk operation error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in bulk update: {e}")
            raise BulkOperationError(f"Failed to perform bulk update: {str(e)}")
    
    async def get_athlete_media(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get athlete's media"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            media = await self.media_repository.query(filters)
            return media
            
        except DatabaseError as e:
            logger.error(f"Database error getting athlete media for {athlete_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athlete media for {athlete_id}: {e}")
            raise StatisticsError(f"Failed to get athlete media: {str(e)}")
    
    async def get_athlete_stats(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get athlete's stats and achievements"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            stats = await self.stats_repository.query(filters)
            return stats
            
        except DatabaseError as e:
            logger.error(f"Database error getting athlete stats for {athlete_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athlete stats for {athlete_id}: {e}")
            raise StatisticsError(f"Failed to get athlete stats: {str(e)}")
    
    # Private helper methods
    
    async def _update_single_athlete(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a single athlete profile - helper method for batch operations"""
        try:
            await self.athlete_repository.update_by_field("user_id", user_id, update_data)
            return True
        except Exception as e:
            logger.error(f"Error updating athlete {user_id}: {e}")
            raise
    
    def _validate_update_data(self, update: Dict[str, Any]) -> bool:
        """Validate update data structure"""
        required_fields = ["user_id", "data"]
        return all(field in update for field in required_fields) and isinstance(update.get("data"), dict)
    
    async def _get_age_group_statistics(self) -> Dict[str, int]:
        """Get athlete count by age groups"""
        try:
            today = date.today()
            age_groups = {
                "junior": {"min_age": 13, "max_age": 18},
                "intermediate": {"min_age": 19, "max_age": 22},
                "senior": {"min_age": 23, "max_age": 30},
                "veteran": {"min_age": 31, "max_age": 100}
            }
            
            age_stats = {}
            for group_name, age_range in age_groups.items():
                min_date = today - relativedelta(years=age_range["max_age"])
                max_date = today - relativedelta(years=age_range["min_age"])
                
                age_filters = [
                    FieldFilter("is_active", "==", True),
                    FieldFilter("date_of_birth", ">=", min_date.isoformat()),
                    FieldFilter("date_of_birth", "<=", max_date.isoformat())
                ]
                
                count = await self.athlete_repository.count(age_filters)
                age_stats[group_name] = count
            
            return age_stats
            
        except Exception as e:
            logger.warning(f"Error getting age group statistics: {e}")
            return {}
    
    async def _get_sport_category_statistics(self) -> Dict[str, int]:
        """Get athlete count by sport category"""
        try:
            # Get all active athletes with sport categories
            active_filters = [FieldFilter("is_active", "==", True)]
            athletes = await self.athlete_repository.query(active_filters, self.statistics_limits['max_sample_size'])
            
            sport_counts = {}
            for athlete in athletes:
                sport_id = athlete.get("primary_sport_category_id")
                if sport_id:
                    sport_counts[sport_id] = sport_counts.get(sport_id, 0) + 1
            
            return sport_counts
            
        except Exception as e:
            logger.warning(f"Error getting sport category statistics: {e}")
            return {}
    
    async def _get_profile_completion_statistics(self) -> Dict[str, int]:
        """Get profile completion distribution"""
        try:
            # Get all active athletes
            active_filters = [FieldFilter("is_active", "==", True)]
            athletes = await self.athlete_repository.query(active_filters, self.statistics_limits['max_sample_size'])
            
            completion_ranges = {
                "0-20%": 0,
                "21-40%": 0,
                "41-60%": 0,
                "61-80%": 0,
                "81-100%": 0
            }
            
            for athlete in athletes:
                completion = self._calculate_completion_percentage(athlete)
                
                if completion <= 20:
                    completion_ranges["0-20%"] += 1
                elif completion <= 40:
                    completion_ranges["21-40%"] += 1
                elif completion <= 60:
                    completion_ranges["41-60%"] += 1
                elif completion <= 80:
                    completion_ranges["61-80%"] += 1
                else:
                    completion_ranges["81-100%"] += 1
            
            return completion_ranges
            
        except Exception as e:
            logger.warning(f"Error getting profile completion statistics: {e}")
            return {}
    
    def _calculate_completion_percentage(self, profile_doc: Dict[str, Any]) -> int:
        """Calculate profile completion percentage"""
        field_weights = self.config['field_weights']
        total_weight = sum(field_weights.values())
        filled_weight = sum(
            field_weights[field] for field, value in profile_doc.items() 
            if field in field_weights and value is not None and value != ""
        )
        
        return int((filled_weight / total_weight) * 100) if total_weight > 0 else 0
    
    async def _get_profile_views(self, athlete_id: str) -> int:
        """Get profile view count for athlete"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            total_views = await self.profile_views_repository.count(filters)
            return total_views
            
        except DatabaseError as e:
            logger.warning(f"Database error getting profile views for athlete {athlete_id}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error getting profile views for athlete {athlete_id}: {e}")
            return 0
    
    async def _get_message_count(self, athlete_id: str) -> int:
        """Get message count for athlete"""
        try:
            # Get messages where athlete is the recipient
            recipient_filters = [FieldFilter("recipient_id", "==", athlete_id)]
            received_count = await self.messages_repository.count(recipient_filters)
            return received_count
            
        except DatabaseError as e:
            logger.warning(f"Database error getting message count for athlete {athlete_id}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error getting message count for athlete {athlete_id}: {e}")
            return 0
    
    async def _get_opportunities_applied(self, athlete_id: str) -> int:
        """Get opportunities applied count for athlete"""
        try:
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            total_applications = await self.applications_repository.count(filters)
            return total_applications
            
        except DatabaseError as e:
            logger.warning(f"Database error getting opportunities applied for athlete {athlete_id}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error getting opportunities applied for athlete {athlete_id}: {e}")
            return 0
    
    async def _get_applications_accepted(self, athlete_id: str) -> int:
        """Get applications accepted count for athlete"""
        try:
            filters = [
                FieldFilter("athlete_id", "==", athlete_id),
                FieldFilter("status", "==", "accepted")
            ]
            
            accepted_count = await self.applications_repository.count(filters)
            return accepted_count
            
        except DatabaseError as e:
            logger.warning(f"Database error getting accepted applications for athlete {athlete_id}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error getting accepted applications for athlete {athlete_id}: {e}")
            return 0 