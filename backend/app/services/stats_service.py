"""
Stats Service for Athletes Networking App

This service handles athlete statistics and achievements management.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from functools import lru_cache

from app.services.database_service import DatabaseService
from app.api.exceptions import ResourceNotFoundError, ValidationError, DatabaseError

# Configure logging
logger = logging.getLogger(__name__)


class StatsService:
    """Service for managing athlete statistics and achievements"""
    
    def __init__(self):
        # Initialize database services for different collections
        self.stats_db = DatabaseService("athlete_stats")
        self.categories_db = DatabaseService("sport_categories")
        
        # Cache configuration
        self._cache = {}
        self._cache_lock = asyncio.Lock()
        self._cache_ttl = timedelta(minutes=15)
        self._max_cache_size = 1000
    
    async def _get_cached_stats(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached stats data"""
        async with self._cache_lock:
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if datetime.now() - cached_data["cached_at"] < self._cache_ttl:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached_data["data"]
                else:
                    # Remove expired cache entry
                    del self._cache[cache_key]
                    logger.debug(f"Cache expired for key: {cache_key}")
            return None
    
    async def _set_cached_stats(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """Set cached stats data with size management"""
        async with self._cache_lock:
            # Manage cache size
            if len(self._cache) >= self._max_cache_size:
                # Remove 20% oldest entries
                sorted_cache = sorted(self._cache.items(), key=lambda item: item[1]['cached_at'])
                num_to_remove = self._max_cache_size // 5
                for i in range(num_to_remove):
                    del self._cache[sorted_cache[i][0]]
                logger.info(f"Cache size exceeded. Removed {num_to_remove} oldest entries.")
            
            self._cache[cache_key] = {
                "data": data,
                "cached_at": datetime.now()
            }
            logger.debug(f"Cached data for key: {cache_key}")
    
    async def _invalidate_stats_cache(self, athlete_id: str) -> None:
        """Invalidate cache for specific athlete"""
        async with self._cache_lock:
            keys_to_remove = [key for key in self._cache.keys() if athlete_id in key]
            for key in keys_to_remove:
                del self._cache[key]
            logger.debug(f"Invalidated cache for athlete: {athlete_id}")
    
    async def create_stats(self, stats_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new stats record for an athlete
        
        Args:
            stats_data: Stats data including athlete_id, sport_category_id, etc.
            
        Returns:
            Created stats record
        """
        try:
            logger.info(f"Creating stats record for athlete: {stats_data.get('athlete_id')}")
            
            # Validate required fields
            required_fields = ['athlete_id', 'sport_category_id', 'season', 'stats']
            missing_fields = [field for field in required_fields if field not in stats_data]
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Validate sport category
            await self.validate_sport_category(stats_data['sport_category_id'])
            
            # Validate stats data
            await self.validate_stats_data(
                stats_data['sport_category_id'],
                stats_data['stats']
            )
            
            stats_record = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                **stats_data
            }
            
            # Use the correct database method
            doc_id = await self.stats_db.create(stats_record, stats_record["id"])
            result = await self.stats_db.get_by_id(doc_id)
            
            # Invalidate cache for this athlete
            await self._invalidate_stats_cache(stats_data['athlete_id'])
            
            logger.info(f"Successfully created stats record: {result['id']}")
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating stats record: {str(e)}")
            raise DatabaseError(f"Failed to create stats record: {str(e)}")
    
    async def get_athlete_stats(
        self,
        athlete_id: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get paginated stats records for an athlete
        
        Args:
            athlete_id: ID of the athlete
            filters: Optional additional filters
            limit: Number of records to return
            offset: Number of records to skip
            
        Returns:
            Paginated stats records
        """
        try:
            logger.info(f"Fetching stats for athlete: {athlete_id}, limit: {limit}, offset: {offset}")
            
            # Create cache key with better hashing
            import hashlib
            filters_str = str(sorted(filters.items())) if filters else ""
            cache_key = f"athlete_stats_{athlete_id}_{hashlib.md5(filters_str.encode()).hexdigest()}_{limit}_{offset}"
            
            # Check cache first
            cached_result = await self._get_cached_stats(cache_key)
            if cached_result:
                return cached_result
            
            # Build query filters
            from firebase_admin.firestore import FieldFilter
            query_filters = [FieldFilter("athlete_id", "==", athlete_id)]
            
            if filters:
                for key, value in filters.items():
                    if key != "athlete_id":  # Already added
                        query_filters.append(FieldFilter(key, "==", value))
            
            # Get total count
            total_records = await self.stats_db.count(query_filters)
            
            # Get paginated results
            records = await self.stats_db.query(query_filters, limit=limit, offset=offset)
            
            result = {
                "count": total_records,
                "results": records,
                "limit": limit,
                "offset": offset,
                "has_next": (offset + limit) < total_records,
                "has_previous": offset > 0
            }
            
            # Cache the result
            await self._set_cached_stats(cache_key, result)
            
            logger.info(f"Retrieved {len(records)} stats records for athlete: {athlete_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching stats for athlete {athlete_id}: {str(e)}")
            raise DatabaseError(f"Failed to fetch athlete stats: {str(e)}")
    
    async def get_stats_by_id(self, stats_id: str) -> Dict[str, Any]:
        """
        Get a specific stats record by ID
        
        Args:
            stats_id: ID of the stats record
            
        Returns:
            Stats record
        """
        try:
            logger.info(f"Fetching stats record: {stats_id}")
            
            stats = await self.stats_db.get_by_id(stats_id)
            if not stats:
                logger.warning(f"Stats record not found: {stats_id}")
                raise ResourceNotFoundError(f"Stats record with ID {stats_id} not found", stats_id)
            
            logger.info(f"Successfully retrieved stats record: {stats_id}")
            return stats
            
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving stats {stats_id}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve stats record: {str(e)}")
    
    async def update_stats(
        self,
        stats_id: str,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a stats record
        
        Args:
            stats_id: ID of the stats record
            update_data: Data to update
            
        Returns:
            Updated stats record
        """
        try:
            logger.info(f"Updating stats record: {stats_id}")
            
            # Get existing record to validate
            existing_record = await self.get_stats_by_id(stats_id)
            
            # Validate sport category if being updated
            if 'sport_category_id' in update_data:
                await self.validate_sport_category(update_data['sport_category_id'])
            
            # Validate stats data if being updated
            if 'stats' in update_data:
                sport_category_id = update_data.get('sport_category_id', existing_record.get('sport_category_id'))
                await self.validate_stats_data(sport_category_id, update_data['stats'])
            
            update_data["updated_at"] = datetime.now().isoformat()
            
            await self.stats_db.update(stats_id, update_data)
            
            # Invalidate cache for this athlete
            athlete_id = existing_record.get('athlete_id')
            if athlete_id:
                await self._invalidate_stats_cache(athlete_id)
            
            result = await self.get_stats_by_id(stats_id)
            logger.info(f"Successfully updated stats record: {stats_id}")
            return result
            
        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"Error updating stats {stats_id}: {str(e)}")
            raise DatabaseError(f"Failed to update stats record: {str(e)}")
    
    async def delete_stats(self, stats_id: str) -> None:
        """
        Delete a stats record
        
        Args:
            stats_id: ID of the stats record
        """
        try:
            logger.info(f"Deleting stats record: {stats_id}")
            
            # Get existing record to get athlete_id for cache invalidation
            existing_record = await self.get_stats_by_id(stats_id)
            athlete_id = existing_record.get('athlete_id')
            
            await self.stats_db.delete(stats_id)
            
            # Invalidate cache for this athlete
            if athlete_id:
                await self._invalidate_stats_cache(athlete_id)
            
            logger.info(f"Successfully deleted stats record: {stats_id}")
            
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting stats {stats_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete stats record: {str(e)}")
    
    async def bulk_create_stats(self, stats_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create multiple stats records efficiently
        
        Args:
            stats_list: List of stats data dictionaries
            
        Returns:
            List of created stats records
        """
        try:
            logger.info(f"Creating {len(stats_list)} stats records in bulk")
            
            # Validate all records first
            for i, stats_data in enumerate(stats_list):
                try:
                    await self.validate_stats_data(
                        stats_data["sport_category_id"],
                        stats_data["stats"]
                    )
                except ValidationError as e:
                    raise ValidationError(f"Validation error for record {i}: {str(e)}")
            
            # Prepare documents for batch creation
            documents = []
            for stats_data in stats_list:
                doc = {
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    **stats_data
                }
                documents.append(doc)
            
            # Use batch create for efficiency
            doc_ids = await self.stats_db.batch_create(documents)
            
            # Fetch created records
            created_records = []
            for doc_id in doc_ids:
                record = await self.stats_db.get_by_id(doc_id)
                if record:
                    created_records.append(record)
            
            # Invalidate cache for all athletes
            athlete_ids = set(stats.get('athlete_id') for stats in stats_list)
            for athlete_id in athlete_ids:
                if athlete_id:
                    await self._invalidate_stats_cache(athlete_id)
            
            logger.info(f"Successfully created {len(created_records)} stats records")
            return created_records
            
        except Exception as e:
            logger.error(f"Error in bulk create: {str(e)}")
            raise DatabaseError(f"Failed to bulk create stats records: {str(e)}")
    
    async def validate_sport_category(self, sport_category_id: str) -> Dict[str, Any]:
        """
        Validate that a sport category exists and is active
        
        Args:
            sport_category_id: ID of the sport category
            
        Returns:
            Sport category data
        """
        try:
            category = await self.categories_db.get_by_id(sport_category_id)
            if not category:
                raise ValidationError(f"Sport category not found: {sport_category_id}")
            
            if not category.get("is_active", False):
                raise ValidationError(f"Sport category is not active: {sport_category_id}")
            
            return category
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating sport category {sport_category_id}: {str(e)}")
            raise DatabaseError(f"Failed to validate sport category: {str(e)}")
    
    async def validate_stats_data(
        self,
        sport_category_id: str,
        stats_data: Dict[str, Any]
    ) -> None:
        """
        Validate stats data against sport category schema
        
        Args:
            sport_category_id: ID of the sport category
            stats_data: Stats data to validate
        """
        try:
            category = await self.validate_sport_category(sport_category_id)
            stats_fields = category.get("stats_fields", [])
            
            if not stats_data:
                raise ValidationError("Stats data cannot be empty")
            
            # Create a lookup of valid fields
            field_schemas = {field["key"]: field for field in stats_fields}
            
            # Validate each stat
            for key, value in stats_data.items():
                if key not in field_schemas:
                    raise ValidationError(f"Invalid stats field: {key}")
                
                field_schema = field_schemas[key]
                
                # Type validation
                expected_type = field_schema["type"]
                if expected_type == "integer" and not isinstance(value, int):
                    raise ValidationError(f"Field {key} must be an integer")
                elif expected_type == "float" and not isinstance(value, (int, float)):
                    raise ValidationError(f"Field {key} must be a number")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    raise ValidationError(f"Field {key} must be a boolean")
                elif expected_type == "string" and not isinstance(value, str):
                    raise ValidationError(f"Field {key} must be a string")
                
                # Range validation
                validation = field_schema.get("validation", {})
                if "min" in validation and value < validation["min"]:
                    raise ValidationError(f"Field {key} must be at least {validation['min']}")
                if "max" in validation and value > validation["max"]:
                    raise ValidationError(f"Field {key} must be at most {validation['max']}")
                
                # Pattern validation for strings
                if expected_type == "string" and "pattern" in validation:
                    import re
                    if not re.match(validation["pattern"], str(value)):
                        raise ValidationError(f"Field {key} does not match required pattern")
            
            # Check required fields
            required_fields = [field["key"] for field in stats_fields if field.get("required", False)]
            missing_fields = [field for field in required_fields if field not in stats_data]
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating stats data: {str(e)}")
            raise DatabaseError(f"Failed to validate stats data: {str(e)}")
    
    async def get_athlete_stats_summary(self, athlete_id: str) -> Dict[str, Any]:
        """
        Get a summary of athlete's stats across all sports and seasons
        
        Args:
            athlete_id: ID of the athlete
            
        Returns:
            Stats summary
        """
        try:
            logger.info(f"Generating stats summary for athlete: {athlete_id}")
            
            # Get stats with reasonable limit to avoid performance issues
            stats_result = await self.get_athlete_stats(athlete_id, limit=100)  # Reduced from 1000
            categories = await self._get_sport_categories()
            
            stats_records = stats_result["results"]
            
            if not stats_records:
                return {
                    "total_seasons": 0,
                    "sports_played": [],
                    "achievements_count": 0,
                    "recent_stats": [],
                    "performance_trends": {}
                }
            
            # Process in parallel
            summary_tasks = [
                self._calculate_performance_trends(athlete_id, stats_records),
                self._get_achievements_summary(stats_records),
                self._get_sports_summary(stats_records, categories)
            ]
            
            trends, achievements, sports = await asyncio.gather(*summary_tasks)
            
            result = {
                "total_seasons": len(set(r.get("season") for r in stats_records)),
                "sports_played": sports,
                "achievements_count": achievements["total"],
                "recent_stats": stats_records[:3],
                "performance_trends": trends
            }
            
            logger.info(f"Generated stats summary for athlete: {athlete_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating stats summary for athlete {athlete_id}: {str(e)}")
            raise DatabaseError(f"Failed to generate stats summary: {str(e)}")
    
    async def _get_sport_categories(self) -> List[Dict[str, Any]]:
        """Get all sport categories for summary generation"""
        try:
            from firebase_admin.firestore import FieldFilter
            return await self.categories_db.query([FieldFilter("is_active", "==", True)])
        except Exception as e:
            logger.error(f"Error fetching sport categories: {str(e)}")
            return []
    
    async def _get_achievements_summary(self, stats_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get achievements summary from stats records"""
        total_achievements = 0
        achievement_types = set()
        
        for record in stats_records:
            achievements = record.get("achievements", [])
            total_achievements += len(achievements)
            for achievement in achievements:
                achievement_types.add(achievement.get("type", ""))
        
        return {
            "total": total_achievements,
            "types": list(achievement_types)
        }
    
    async def _get_sports_summary(self, stats_records: List[Dict[str, Any]], categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get sports summary with category names"""
        sports_played = set()
        sports_summary = []
        
        for record in stats_records:
            sport_id = record.get("sport_category_id")
            if sport_id:
                sports_played.add(sport_id)
        
        # Add category names
        category_map = {cat["id"]: cat["name"] for cat in categories}
        for sport_id in sports_played:
            sports_summary.append({
                "id": sport_id,
                "name": category_map.get(sport_id, "Unknown Sport")
            })
        
        return sports_summary
    
    async def _calculate_performance_trends(
        self,
        athlete_id: str,
        stats_records: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate performance trends for an athlete
        
        Args:
            athlete_id: ID of the athlete
            stats_records: List of stats records
            
        Returns:
            Performance trends analysis
        """
        if len(stats_records) < 2:
            return {"trend": "insufficient_data"}
        
        # Group by sport category
        by_sport = {}
        for record in stats_records:
            sport_id = record.get("sport_category_id")
            if sport_id:
                if sport_id not in by_sport:
                    by_sport[sport_id] = []
                by_sport[sport_id].append(record)
        
        trends = {}
        
        for sport_id, records in by_sport.items():
            if len(records) >= 2:
                # Sort by season/date
                sorted_records = sorted(records, key=lambda x: x.get("season", ""))
                
                # Simple trend calculation (comparing first and last records)
                first_record = sorted_records[0]
                last_record = sorted_records[-1]
                
                trends[sport_id] = {
                    "seasons_tracked": len(sorted_records),
                    "improvement_indicators": self._compare_stats(first_record, last_record)
                }
        
        return trends
    
    def _compare_stats(
        self,
        old_record: Dict[str, Any],
        new_record: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Compare two stats records to identify improvements
        
        Args:
            old_record: Older stats record
            new_record: Newer stats record
            
        Returns:
            Comparison results
        """
        old_stats = old_record.get("stats", {})
        new_stats = new_record.get("stats", {})
        
        improvements = {}
        
        for key in old_stats:
            if key in new_stats:
                old_value = old_stats[key]
                new_value = new_stats[key]
                
                if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                    if new_value > old_value:
                        improvements[key] = "improved"
                    elif new_value < old_value:
                        improvements[key] = "declined"
                    else:
                        improvements[key] = "stable"
        
        return improvements
    
    async def get_top_performers(
        self,
        sport_category_id: str,
        stat_field: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top performers in a specific stat field
        
        Args:
            sport_category_id: ID of the sport category
            stat_field: The stat field to rank by
            limit: Number of top performers to return
            
        Returns:
            List of top performers
        """
        try:
            logger.info(f"Getting top performers for sport {sport_category_id}, field {stat_field}")
            
            # Get all stats for the sport category
            from firebase_admin.firestore import FieldFilter
            stats_records = await self.stats_db.query([FieldFilter("sport_category_id", "==", sport_category_id)])
            
            # Extract and sort by the stat field
            performers = []
            for record in stats_records:
                stats = record.get("stats", {})
                if stat_field in stats:
                    value = stats[stat_field]
                    if isinstance(value, (int, float)):
                        performers.append({
                            "athlete_id": record["athlete_id"],
                            "season": record.get("season", ""),
                            "team_name": record.get("team_name", ""),
                            "value": value,
                            "stats_record": record
                        })
            
            # Sort by value (descending) and return top performers
            performers.sort(key=lambda x: x["value"], reverse=True)
            result = performers[:limit]
            
            logger.info(f"Found {len(result)} top performers")
            return result
            
        except Exception as e:
            logger.error(f"Error getting top performers: {str(e)}")
            raise DatabaseError(f"Failed to get top performers: {str(e)}")
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries and return number of removed entries"""
        try:
            async with self._cache_lock:
                current_time = datetime.now()
                expired_keys = []
                
                for key, data in self._cache.items():
                    if current_time - data["cached_at"] > self._cache_ttl:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self._cache[key]
                
                if expired_keys:
                    logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
                return len(expired_keys)
                
        except Exception as e:
            logger.error(f"Error cleaning up cache: {str(e)}")
            return 0 