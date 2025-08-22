"""
Refactored Athlete Service - Main orchestrator service that coordinates specialized services
"""
from typing import Optional, Dict, Any, List, Callable
import logging
import asyncio
import time
from datetime import datetime, timezone
from functools import wraps

from ..models.athlete import AthleteProfileCreate, AthleteProfileUpdate, AthleteSearchFilters, AthleteAnalytics
from ..models.base import PaginatedResponse
from .exceptions import AthleteServiceError
from .athlete_profile_service import AthleteProfileService
from .athlete_search_service import AthleteSearchService
from .athlete_recommendation_service import AthleteRecommendationService
from .athlete_analytics_service import AthleteAnalyticsService
from ..config.athlete_config import get_athlete_config
from ..utils.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class AthleteServiceConfig:
    """Configuration constants for AthleteService"""
    
    # Performance thresholds (in milliseconds)
    SLOW_OPERATION_THRESHOLDS = {
        'profile_creation': 2000,
        'profile_update': 2000,
        'profile_retrieval': 1000,
        'profile_deletion': 1000,
        'profile_restoration': 1000,
        'completion_retrieval': 1000,
        'search_operation': 1000,
        'sport_category_query': 1000,
        'location_query': 1000,
        'age_range_query': 1000,
        'count_query': 500,
        'recommendation_query': 2000,
        'preference_query': 2000,
        'similarity_query': 2000,
        'analytics_query': 1000,
        'statistics_query': 2000,
        'bulk_operation': 5000,
        'media_query': 1000,
        'stats_query': 1000,
        'athlete_retrieval': 1000
    }
    
    # Default limits
    DEFAULT_LIMITS = {
        'max_search_limit': 100,
        'max_bulk_update': 1000,
        'min_age': 10,
        'max_age': 50,
        'default_recommendation_limit': 20,
        'default_preference_limit': 20,
        'default_similarity_limit': 10
    }


def validate_user_id(func: Callable) -> Callable:
    """Decorator to validate user_id parameter"""
    @wraps(func)
    async def wrapper(self, user_id: str, *args, **kwargs):
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        return await func(self, user_id, *args, **kwargs)
    return wrapper


def validate_athlete_id(func: Callable) -> Callable:
    """Decorator to validate athlete_id parameter"""
    @wraps(func)
    async def wrapper(self, athlete_id: str, *args, **kwargs):
        if not athlete_id or not athlete_id.strip():
            raise ValueError("athlete_id cannot be empty")
        return await func(self, athlete_id, *args, **kwargs)
    return wrapper


def validate_pagination_params(func: Callable) -> Callable:
    """Decorator to validate pagination parameters"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # Extract limit and offset from kwargs or inspect function signature
        import inspect
        
        # Get function signature to understand parameter order
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        
        # Find limit and offset parameters by name, regardless of position
        limit = None
        offset = 0
        
        # Check kwargs first
        if 'limit' in kwargs:
            limit = kwargs['limit']
        if 'offset' in kwargs:
            offset = kwargs['offset']
        
        # If not in kwargs, check positional arguments
        if limit is None and 'limit' in params:
            limit_idx = params.index('limit')
            if limit_idx < len(args):
                limit = args[limit_idx]
        
        if offset == 0 and 'offset' in params:
            offset_idx = params.index('offset')
            if offset_idx < len(args):
                offset = args[offset_idx]
        
        # Use configuration for limits
        max_limit = self.config.get('search_limits', {}).get('max_limit', AthleteServiceConfig.DEFAULT_LIMITS['max_search_limit'])
        if limit is not None and (limit < 1 or limit > max_limit):
            raise ValueError(f"limit must be between 1 and {max_limit}")
        
        if offset < 0:
            raise ValueError("offset cannot be negative")
        
        return await func(self, *args, **kwargs)
    return wrapper


def validate_age_range(func: Callable) -> Callable:
    """Decorator to validate age range parameters"""
    @wraps(func)
    async def wrapper(self, min_age: int, max_age: int, *args, **kwargs):
        # Use configuration for age limits
        age_limits = self.config.get('age_limits', {})
        min_age_limit = age_limits.get('min_age', AthleteServiceConfig.DEFAULT_LIMITS['min_age'])
        max_age_limit = age_limits.get('max_age', AthleteServiceConfig.DEFAULT_LIMITS['max_age'])
        
        if min_age < min_age_limit or min_age > max_age_limit:
            raise ValueError(f"min_age must be between {min_age_limit} and {max_age_limit}")
        if max_age < min_age_limit or max_age > max_age_limit:
            raise ValueError(f"max_age must be between {min_age_limit} and {max_age_limit}")
        if min_age > max_age:
            raise ValueError("min_age cannot be greater than max_age")
        
        return await func(self, min_age, max_age, *args, **kwargs)
    return wrapper


def validate_bulk_operations(func: Callable) -> Callable:
    """Decorator to validate bulk operation parameters"""
    @wraps(func)
    async def wrapper(self, updates: List[Dict[str, Any]], *args, **kwargs):
        if not updates:
            raise ValueError("updates list cannot be empty")
        
        # Use configuration for bulk limits
        max_bulk_update = self.config.get('bulk_limits', {}).get('max_bulk_update', AthleteServiceConfig.DEFAULT_LIMITS['max_bulk_update'])
        if len(updates) > max_bulk_update:
            raise ValueError(f"updates list cannot exceed {max_bulk_update} items")
        
        return await func(self, updates, *args, **kwargs)
    return wrapper


def validate_preferences(func: Callable) -> Callable:
    """Decorator to validate preferences parameter"""
    @wraps(func)
    async def wrapper(self, preferences: Dict[str, Any], *args, **kwargs):
        if not preferences:
            raise ValueError("preferences cannot be empty")
        return await func(self, preferences, *args, **kwargs)
    return wrapper


def validate_filters(func: Callable) -> Callable:
    """Decorator to validate filters parameter"""
    @wraps(func)
    async def wrapper(self, filters, *args, **kwargs):
        if not filters:
            raise ValueError("filters cannot be None")
        return await func(self, filters, *args, **kwargs)
    return wrapper


def validate_scout_id(func: Callable) -> Callable:
    """Decorator to validate scout_id parameter"""
    @wraps(func)
    async def wrapper(self, scout_id: str, *args, **kwargs):
        if not scout_id or not scout_id.strip():
            raise ValueError("scout_id cannot be empty")
        return await func(self, scout_id, *args, **kwargs)
    return wrapper


def validate_location(func: Callable) -> Callable:
    """Decorator to validate location parameter"""
    @wraps(func)
    async def wrapper(self, location: str, *args, **kwargs):
        if not location or not location.strip():
            raise ValueError("location cannot be empty")
        return await func(self, location, *args, **kwargs)
    return wrapper


def validate_sport_category(func: Callable) -> Callable:
    """Decorator to validate sport_category_id parameter"""
    @wraps(func)
    async def wrapper(self, sport_category_id: str, *args, **kwargs):
        if not sport_category_id or not sport_category_id.strip():
            raise ValueError("sport_category_id cannot be empty")
        return await func(self, sport_category_id, *args, **kwargs)
    return wrapper


class AthleteService:
    """
    Main Athlete Service that orchestrates specialized services
    
    This service provides a unified interface to all athlete-related operations
    while delegating specific functionality to specialized services.
    """
    
    def __init__(self, environment: str = None):
        """Initialize AthleteService with specialized services"""
        try:
            self.config = get_athlete_config()
            self._validate_config()
            
            # Initialize performance monitor with thresholds from config
            self.performance_monitor = PerformanceMonitor(
                threshold_ms=max(AthleteServiceConfig.SLOW_OPERATION_THRESHOLDS.values()),
                enable_logging=True
            )
            
            # Initialize specialized services with individual error handling
            try:
                self.profile_service = AthleteProfileService(environment)
            except Exception as e:
                logger.error(f"Failed to initialize profile service: {e}", exc_info=True)
                raise AthleteServiceError(f"Profile service initialization failed: {str(e)}")
            
            try:
                self.search_service = AthleteSearchService(environment)
            except Exception as e:
                logger.error(f"Failed to initialize search service: {e}", exc_info=True)
                raise AthleteServiceError(f"Search service initialization failed: {str(e)}")
            
            try:
                self.recommendation_service = AthleteRecommendationService(environment)
            except Exception as e:
                logger.error(f"Failed to initialize recommendation service: {e}", exc_info=True)
                raise AthleteServiceError(f"Recommendation service initialization failed: {str(e)}")
            
            try:
                self.analytics_service = AthleteAnalyticsService(environment)
            except Exception as e:
                logger.error(f"Failed to initialize analytics service: {e}", exc_info=True)
                raise AthleteServiceError(f"Analytics service initialization failed: {str(e)}")
            
            logger.info("AthleteService initialized with specialized services")
        except Exception as e:
            logger.error(f"Failed to initialize AthleteService: {e}", exc_info=True)
            raise AthleteServiceError(f"Service initialization failed: {str(e)}")
    
    def _validate_config(self):
        """Validate required configuration keys and values exist"""
        required_keys = ['collections', 'search_limits', 'bulk_limits', 'statistics_limits', 'performance']
        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")
        
        # Validate nested configuration values
        if not self.config.get('search_limits', {}).get('max_limit'):
            raise ValueError("search_limits.max_limit must be configured")
        
        if not self.config.get('bulk_limits', {}).get('max_bulk_update'):
            raise ValueError("bulk_limits.max_bulk_update must be configured")
        
        if not self.config.get('collections'):
            raise ValueError("collections configuration must be provided")
        
        # Validate performance configuration
        performance_config = self.config.get('performance', {})
        if 'enable_caching' not in performance_config:
            logger.warning("performance.enable_caching not configured, defaulting to False")
        
        # Validate age limits if present
        age_limits = self.config.get('age_limits', {})
        if age_limits:
            if 'min_age' in age_limits and 'max_age' in age_limits:
                if age_limits['min_age'] >= age_limits['max_age']:
                    raise ValueError("age_limits.min_age must be less than age_limits.max_age")
        
        logger.info("Configuration validation completed successfully")
    
    # Profile Management Methods (delegated to AthleteProfileService)
    
    @PerformanceMonitor.monitor("profile_creation")
    @validate_user_id
    async def create_athlete_profile(self, user_id: str, profile_data: AthleteProfileCreate) -> Dict[str, Any]:
        """
        Create athlete profile
        
        Args:
            user_id: The unique identifier of the user
            profile_data: Data for creating the athlete profile
            
        Returns:
            Dict containing the created athlete profile data
            
        Raises:
            AthleteServiceError: If profile creation fails
        """
        try:
            result = await self.profile_service.create_athlete_profile(user_id, profile_data)
            return result
        except ValueError as e:
            logger.warning(f"Validation error creating athlete profile for user {user_id}: {e}", 
                         extra={'user_id': user_id, 'operation': 'create_profile', 'error_type': 'validation'})
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create athlete profile for user {user_id}: {e}", 
                        extra={'user_id': user_id, 'operation': 'create_profile', 'error_type': 'system'}, exc_info=True)
            raise AthleteServiceError(f"Profile creation failed for user {user_id}: {str(e)}")
    
    @PerformanceMonitor.monitor("profile_retrieval")
    @validate_user_id
    async def get_athlete_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get athlete profile by user ID
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            Dict containing athlete profile data or None if not found
            
        Raises:
            AthleteServiceError: If profile retrieval fails
        """
        try:
            result = await self.profile_service.get_athlete_profile(user_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athlete profile for user {user_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Profile retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("profile_update")
    @validate_user_id
    async def update_athlete_profile(self, user_id: str, profile_data: AthleteProfileUpdate) -> Dict[str, Any]:
        """
        Update athlete profile
        
        Args:
            user_id: The unique identifier of the user
            profile_data: Data for updating the athlete profile
            
        Returns:
            Dict containing the updated athlete profile data
            
        Raises:
            AthleteServiceError: If profile update fails
        """
        try:
            result = await self.profile_service.update_athlete_profile(user_id, profile_data)
            return result
        except ValueError as e:
            logger.warning(f"Validation error updating athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to update athlete profile for user {user_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Profile update failed: {str(e)}")
    
    @PerformanceMonitor.monitor("profile_deletion")
    @validate_user_id
    async def delete_athlete_profile(self, user_id: str) -> bool:
        """
        Soft delete athlete profile
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            True if profile was successfully deleted
            
        Raises:
            AthleteServiceError: If profile deletion fails
        """
        try:
            result = await self.profile_service.delete_athlete_profile(user_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error deleting athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to delete athlete profile for user {user_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Profile deletion failed: {str(e)}")
    
    @PerformanceMonitor.monitor("profile_restoration")
    @validate_user_id
    async def restore_athlete_profile(self, user_id: str) -> bool:
        """
        Restore a soft-deleted athlete profile
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            True if profile was successfully restored
            
        Raises:
            AthleteServiceError: If profile restoration fails
        """
        try:
            result = await self.profile_service.restore_athlete_profile(user_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error restoring athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to restore athlete profile for user {user_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Profile restoration failed: {str(e)}")
    
    @PerformanceMonitor.monitor("completion_retrieval")
    @validate_user_id
    async def get_athlete_profile_completion(self, user_id: str) -> Dict[str, Any]:
        """
        Get detailed profile completion information
        
        Args:
            user_id: The unique identifier of the user
            
        Returns:
            Dict containing profile completion details
            
        Raises:
            AthleteServiceError: If completion retrieval fails
        """
        try:
            result = await self.profile_service.get_athlete_profile_completion(user_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting profile completion for user {user_id}: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get profile completion for user {user_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Completion retrieval failed: {str(e)}")
    
    # Search and Filtering Methods (delegated to AthleteSearchService)
    
    @PerformanceMonitor.monitor("search_operation")
    @validate_filters
    async def search_athletes(self, filters: AthleteSearchFilters) -> PaginatedResponse:
        """
        Search athletes with optimized filtering and validation
        
        Args:
            filters: Search filters for finding athletes
            
        Returns:
            PaginatedResponse containing search results
            
        Raises:
            AthleteServiceError: If search operation fails
        """
        try:
            result = await self.search_service.search_athletes(filters)
            return result
        except ValueError as e:
            logger.warning(f"Validation error in athlete search: {e}", 
                         extra={'operation': 'search_athletes', 'error_type': 'validation', 'filters': str(filters)})
            raise AthleteServiceError(f"Invalid search filters: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to search athletes: {e}", 
                        extra={'operation': 'search_athletes', 'error_type': 'system', 'filters': str(filters)}, exc_info=True)
            raise AthleteServiceError(f"Search operation failed: {str(e)}")
    
    @PerformanceMonitor.monitor("sport_category_query")
    @validate_sport_category
    @validate_pagination_params
    async def get_athletes_by_sport_category(self, sport_category_id: str, limit: int = None, offset: int = 0) -> PaginatedResponse:
        """
        Get athletes by sport category with pagination
        
        Args:
            sport_category_id: The sport category identifier
            limit: Maximum number of results to return (default: None)
            offset: Number of results to skip (default: 0)
            
        Returns:
            PaginatedResponse containing athletes in the specified sport category
            
        Raises:
            AthleteServiceError: If retrieval fails
        """
        try:
            result = await self.search_service.get_athletes_by_sport_category(sport_category_id, limit, offset)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athletes by sport category: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athletes by sport category {sport_category_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("location_query")
    @validate_location
    @validate_pagination_params
    async def get_athletes_by_location(self, location: str, limit: int = None, offset: int = 0) -> PaginatedResponse:
        """
        Get athletes by location with pagination
        
        Args:
            location: The location to search for athletes
            limit: Maximum number of results to return (default: None)
            offset: Number of results to skip (default: 0)
            
        Returns:
            PaginatedResponse containing athletes in the specified location
            
        Raises:
            AthleteServiceError: If retrieval fails
        """
        try:
            result = await self.search_service.get_athletes_by_location(location, limit, offset)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athletes by location: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athletes by location {location}: {e}", exc_info=True)
            raise AthleteServiceError(f"Retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("age_range_query")
    @validate_age_range
    @validate_pagination_params
    async def get_athletes_by_age_range(self, min_age: int, max_age: int, limit: int = None, offset: int = 0) -> PaginatedResponse:
        """
        Get athletes by age range with pagination
        
        Args:
            min_age: Minimum age for the search range
            max_age: Maximum age for the search range
            limit: Maximum number of results to return (default: None)
            offset: Number of results to skip (default: 0)
            
        Returns:
            PaginatedResponse containing athletes in the specified age range
            
        Raises:
            AthleteServiceError: If retrieval fails
        """
        try:
            result = await self.search_service.get_athletes_by_age_range(min_age, max_age, limit, offset)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athletes by age range: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athletes by age range {min_age}-{max_age}: {e}", exc_info=True)
            raise AthleteServiceError(f"Retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("count_query")
    async def get_active_athletes_count(self) -> int:
        """
        Get total count of active athletes
        
        Returns:
            Number of active athletes
            
        Raises:
            AthleteServiceError: If count retrieval fails
        """
        try:
            result = await self.search_service.get_active_athletes_count()
            return result
        except Exception as e:
            logger.error(f"Failed to get active athletes count: {e}", exc_info=True)
            raise AthleteServiceError(f"Count retrieval failed: {str(e)}")
    
    # Recommendation Methods (delegated to AthleteRecommendationService)
    
    @PerformanceMonitor.monitor("recommendation_query")
    @validate_scout_id
    async def get_recommended_athletes(self, scout_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get recommended athletes for a scout
        
        Args:
            scout_id: The scout's unique identifier
            limit: Maximum number of recommendations to return (default: 20)
            
        Returns:
            List of recommended athlete profiles
            
        Raises:
            AthleteServiceError: If recommendation retrieval fails
        """
        try:
            # Use configuration for limits
            if limit is None:
                limit = AthleteServiceConfig.DEFAULT_LIMITS['default_recommendation_limit']
            
            max_limit = self.config.get('search_limits', {}).get('max_limit', AthleteServiceConfig.DEFAULT_LIMITS['max_search_limit'])
            if limit < 1 or limit > max_limit:
                raise ValueError(f"limit must be between 1 and {max_limit}")
                
            result = await self.recommendation_service.get_recommended_athletes(scout_id, limit)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting recommended athletes: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get recommended athletes for scout {scout_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Recommendation retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("preference_query")
    @validate_preferences
    async def get_athletes_by_preferences(self, preferences: Dict[str, Any], limit: int = None) -> List[Dict[str, Any]]:
        """
        Get athletes based on specific preferences
        
        Args:
            preferences: Dictionary containing preference criteria
            limit: Maximum number of results to return (default: 20)
            
        Returns:
            List of athlete profiles matching the preferences
            
        Raises:
            AthleteServiceError: If preference-based search fails
        """
        try:
            # Use configuration for limits
            if limit is None:
                limit = AthleteServiceConfig.DEFAULT_LIMITS['default_preference_limit']
            
            max_limit = self.config.get('search_limits', {}).get('max_limit', AthleteServiceConfig.DEFAULT_LIMITS['max_search_limit'])
            if limit < 1 or limit > max_limit:
                raise ValueError(f"limit must be between 1 and {max_limit}")
                
            result = await self.recommendation_service.get_athletes_by_preferences(preferences, limit)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athletes by preferences: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athletes by preferences: {e}", exc_info=True)
            raise AthleteServiceError(f"Preference search failed: {str(e)}")
    
    @PerformanceMonitor.monitor("similarity_query")
    @validate_athlete_id
    async def get_similar_athletes(self, athlete_id: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get athletes similar to a given athlete
        
        Args:
            athlete_id: The athlete's unique identifier
            limit: Maximum number of similar athletes to return (default: 10)
            
        Returns:
            List of similar athlete profiles
            
        Raises:
            AthleteServiceError: If similarity search fails
        """
        try:
            # Use configuration for limits
            if limit is None:
                limit = AthleteServiceConfig.DEFAULT_LIMITS['default_similarity_limit']
            
            max_limit = self.config.get('search_limits', {}).get('max_limit', AthleteServiceConfig.DEFAULT_LIMITS['max_search_limit'])
            if limit < 1 or limit > min(50, max_limit):
                raise ValueError(f"limit must be between 1 and {min(50, max_limit)}")
                
            result = await self.recommendation_service.get_similar_athletes(athlete_id, limit)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting similar athletes: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get similar athletes for {athlete_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Similarity search failed: {str(e)}")
    
    # Analytics and Statistics Methods (delegated to AthleteAnalyticsService)
    
    @PerformanceMonitor.monitor("analytics_query")
    @validate_athlete_id
    async def get_athlete_analytics(self, athlete_id: str) -> AthleteAnalytics:
        """
        Get athlete analytics with batch operations
        
        Args:
            athlete_id: The athlete's unique identifier
            
        Returns:
            AthleteAnalytics object containing analytics data
            
        Raises:
            AthleteServiceError: If analytics retrieval fails
        """
        try:
            result = await self.analytics_service.get_athlete_analytics(athlete_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athlete analytics: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get analytics for athlete {athlete_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Analytics retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("statistics_query")
    async def get_athlete_statistics(self) -> Dict[str, Any]:
        """
        Get overall athlete statistics and demographics
        
        Returns:
            Dictionary containing athlete statistics
            
        Raises:
            AthleteServiceError: If statistics retrieval fails
        """
        try:
            result = await self.analytics_service.get_athlete_statistics()
            return result
        except Exception as e:
            logger.error(f"Failed to get athlete statistics: {e}", exc_info=True)
            raise AthleteServiceError(f"Statistics retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("bulk_operation")
    @validate_bulk_operations
    async def bulk_update_athletes(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Bulk update multiple athlete profiles
        
        Args:
            updates: List of update operations for athlete profiles
            
        Returns:
            Dictionary containing bulk update results
            
        Raises:
            AthleteServiceError: If bulk update fails
        """
        try:
            result = await self.analytics_service.bulk_update_athletes(updates)
            return result
        except ValueError as e:
            logger.warning(f"Validation error in bulk update: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to perform bulk update: {e}", exc_info=True)
            raise AthleteServiceError(f"Bulk update failed: {str(e)}")
    
    @PerformanceMonitor.monitor("media_query")
    @validate_athlete_id
    async def get_athlete_media(self, athlete_id: str) -> List[Dict[str, Any]]:
        """
        Get athlete's media
        
        Args:
            athlete_id: The athlete's unique identifier
            
        Returns:
            List of media items associated with the athlete
            
        Raises:
            AthleteServiceError: If media retrieval fails
        """
        try:
            result = await self.analytics_service.get_athlete_media(athlete_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athlete media: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get media for athlete {athlete_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Media retrieval failed: {str(e)}")
    
    @PerformanceMonitor.monitor("stats_query")
    @validate_athlete_id
    async def get_athlete_stats(self, athlete_id: str) -> List[Dict[str, Any]]:
        """
        Get athlete's stats and achievements
        
        Args:
            athlete_id: The athlete's unique identifier
            
        Returns:
            List of stats and achievements for the athlete
            
        Raises:
            AthleteServiceError: If stats retrieval fails
        """
        try:
            result = await self.analytics_service.get_athlete_stats(athlete_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athlete stats: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get stats for athlete {athlete_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Stats retrieval failed: {str(e)}")
    
    # Convenience Methods
    
    @PerformanceMonitor.monitor("athlete_retrieval")
    @validate_athlete_id
    async def get_athlete_by_id(self, athlete_id: str) -> Optional[Dict[str, Any]]:
        """
        Get athlete profile by athlete ID (user ID) - convenience method
        
        Args:
            athlete_id: The athlete's unique identifier
            
        Returns:
            Dict containing athlete profile data or None if not found
            
        Raises:
            AthleteServiceError: If profile retrieval fails
        """
        try:
            result = await self.profile_service.get_athlete_profile(athlete_id)
            return result
        except ValueError as e:
            logger.warning(f"Validation error getting athlete by ID: {e}")
            raise AthleteServiceError(f"Invalid input: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to get athlete by ID {athlete_id}: {e}", exc_info=True)
            raise AthleteServiceError(f"Profile retrieval failed: {str(e)}")
    
    # Service Health and Configuration Methods
    
    def get_service_config(self) -> Dict[str, Any]:
        """
        Get current service configuration
        
        Returns:
            Dictionary containing service configuration details
        """
        return {
            "environment": "production" if self.config.get('performance', {}).get('enable_caching') else "development",
            "services": {
                "profile_service": "initialized",
                "search_service": "initialized",
                "recommendation_service": "initialized",
                "analytics_service": "initialized"
            },
            "performance": self.config.get('performance', {}),
            "limits": {
                "search": self.config.get('search_limits', {}),
                "bulk": self.config.get('bulk_limits', {}),
                "statistics": self.config.get('statistics_limits', {})
            },
            "thresholds": AthleteServiceConfig.SLOW_OPERATION_THRESHOLDS,
            "default_limits": AthleteServiceConfig.DEFAULT_LIMITS
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics from the PerformanceMonitor
        
        Returns:
            Dictionary containing performance metrics for all operations
        """
        return {
            "performance_monitor_metrics": self.performance_monitor.get_metrics(),
            "slow_operations": self.performance_monitor.get_slow_operations(),
            "performance_report": self.performance_monitor.generate_report()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all services
        
        Returns:
            Dictionary containing health status of all services
        """
        try:
            current_time = datetime.now(timezone.utc).isoformat()
            health_status = {
                "status": "healthy",
                "timestamp": current_time,
                "services": {}
            }
            
            async def check_service(service_name: str, health_method) -> str:
                """Helper function to check individual service health"""
                try:
                    await asyncio.wait_for(health_method(), timeout=5.0)
                    return "healthy"
                except asyncio.TimeoutError:
                    return "timeout"
                except Exception as e:
                    return f"unhealthy: {str(e)}"
            
            # Check profile service - use a lightweight health check
            try:
                profile_status = await check_service("profile_service", 
                    lambda: self.profile_service.get_athlete_profile_completion("test_user"))
                health_status["services"]["profile_service"] = profile_status
            except Exception as e:
                health_status["services"]["profile_service"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check search service - use a lightweight health check
            try:
                search_status = await check_service("search_service", 
                    lambda: self.search_service.get_active_athletes_count())
                health_status["services"]["search_service"] = search_status
            except Exception as e:
                health_status["services"]["search_service"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check recommendation service - use a lightweight health check
            try:
                # Try to get a simple recommendation count or use a lightweight method
                rec_status = await check_service("recommendation_service", 
                    lambda: self._check_recommendation_service_health())
                health_status["services"]["recommendation_service"] = rec_status
            except Exception as e:
                health_status["services"]["recommendation_service"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check analytics service - use a lightweight health check
            try:
                analytics_status = await check_service("analytics_service", 
                    lambda: self.analytics_service.get_active_athletes_count())
                health_status["services"]["analytics_service"] = analytics_status
            except Exception as e:
                health_status["services"]["analytics_service"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Update overall status based on service health
            unhealthy_services = [status for status in health_status["services"].values() if status != "healthy"]
            if unhealthy_services:
                if len(unhealthy_services) == len(health_status["services"]):
                    health_status["status"] = "unhealthy"
                else:
                    health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            current_time = datetime.now(timezone.utc).isoformat()
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": current_time
            }
    
    async def _check_recommendation_service_health(self) -> None:
        """
        Lightweight health check for recommendation service
        
        This method provides a consistent way to check if the recommendation service
        is responsive without making heavy database queries.
        """
        try:
            # Try to access a simple property or method that indicates the service is alive
            # This could be checking if the service instance exists and is responsive
            if hasattr(self.recommendation_service, '_is_healthy'):
                # If the service has a health indicator, use it
                if not self.recommendation_service._is_healthy:
                    raise Exception("Service health indicator shows unhealthy state")
            else:
                # Fallback: just check if the service object exists and is callable
                if not callable(getattr(self.recommendation_service, '__class__', None)):
                    raise Exception("Service object is not properly initialized")
        except Exception as e:
            raise Exception(f"Recommendation service health check failed: {str(e)}") 