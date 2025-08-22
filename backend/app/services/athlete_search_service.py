"""
Athlete Search Service - Handles search, filtering, and pagination for athletes
"""
from typing import Optional, Dict, Any, List
import logging
import time
import hashlib
import threading
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from ..models.athlete import AthleteSearchFilters
from ..models.base import PaginatedResponse
from .database_service import DatabaseService, DatabaseError, ValidationError, DatabaseConnectionPool
from .exceptions import AthleteServiceError, InputValidationError
from ..config.athlete_config import get_athlete_config
from ..utils.performance_monitor import PerformanceMonitor
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class AthleteSearchService:
    """Service for searching and filtering athletes"""
    
    def __init__(self, environment: str = None):
        self.config = get_athlete_config()
        self._validate_config()
        self.collections = self.config['collections']
        self.search_limits = self.config['search_limits']
        self.age_limits = self.config['age_limits']
        self.logging_config = self.config['logging']
        self.performance_config = self.config.get('performance', {})
        self.security_config = self.config.get('security', {})
        
        # Initialize repositories
        self.athlete_repository = DatabaseService(self.collections["athlete_profiles"])
        
        # Initialize connection pool
        self.connection_pool = DatabaseConnectionPool(
            max_connections=self.performance_config.get('max_concurrent_queries', 5)
        )
        
        # Initialize caching with thread safety
        self._query_cache = {}
        self.cache_ttl = self.performance_config.get('cache_ttl_seconds', 3600)
        self.max_cache_size = self.performance_config.get('cache_size', 128)
        self._cache_lock = threading.Lock()
        
        # Initialize performance monitor
        self.performance_monitor = PerformanceMonitor(
            threshold_ms=int(self.logging_config.get('slow_query_threshold', 1.0) * 1000),
            enable_logging=self.logging_config.get('log_query_performance', False)
        )
        
        # Performance monitoring
        self._query_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_query_time': 0.0,
            'query_times': []
        }
    
    def _validate_config(self):
        """Validate required configuration keys exist with enhanced validation"""
        required_keys = ['collections', 'search_limits', 'age_limits', 'logging']
        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")
        
        # Validate nested configuration
        if 'collections' not in self.config or 'athlete_profiles' not in self.config['collections']:
            raise ValueError("Missing required collection configuration for athlete_profiles")
        
        if 'search_limits' not in self.config:
            raise ValueError("Missing search_limits configuration")
        
        if 'age_limits' not in self.config:
            raise ValueError("Missing age_limits configuration")
        
        # Validate logging configuration with defaults
        if 'logging' in self.config:
            logging_keys = ['log_search_queries', 'log_query_performance', 'slow_query_threshold', 'slow_count_query_threshold']
            missing_logging_keys = [key for key in logging_keys if key not in self.config['logging']]
            if missing_logging_keys:
                logger.warning(f"Missing logging configuration keys: {missing_logging_keys}")
                # Set defaults for missing keys
                for key in missing_logging_keys:
                    if 'threshold' in key:
                        self.config['logging'][key] = 1.0
                    else:
                        self.config['logging'][key] = False
        
        # Validate performance configuration with defaults
        if 'performance' not in self.config:
            self.config['performance'] = {
                'enable_caching': True,
                'cache_size': 128,
                'cache_ttl_seconds': 3600,
                'enable_batch_processing': True,
                'max_concurrent_queries': 5,
                'enable_query_optimization': True,
                'max_query_timeout': 30
            }
        
        # Validate security configuration with defaults
        if 'security' not in self.config:
            self.config['security'] = {
                'enable_input_validation': True,
                'enable_sanitization': True,
                'max_string_length': 1000,
                'allowed_genders': ['male', 'female', 'other'],
                'enable_rate_limiting': True,
                'max_requests_per_minute': 100,
                'blocked_patterns': ['script', '<', '>', 'javascript'],
                'enable_audit_logging': True
            }
    
    def _sanitize_search_input(self, value: str) -> str:
        """Sanitize search input to prevent injection attacks"""
        if not value or not isinstance(value, str):
            return value
        
        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '{', '}', '[', ']', '\\', '/']
        sanitized = value
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        # Check for blocked patterns
        blocked_patterns = self.security_config.get('blocked_patterns', [])
        for pattern in blocked_patterns:
            if pattern.lower() in sanitized.lower():
                sanitized = sanitized.replace(pattern, '')
        
        # Limit length
        max_length = self.security_config.get('max_string_length', 1000)
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    def _validate_and_sanitize_filters(self, filters: AthleteSearchFilters) -> AthleteSearchFilters:
        """Validate and sanitize all filter inputs"""
        # Create a copy to avoid modifying original
        sanitized_filters = filters.copy()
        
        # Sanitize string fields
        if sanitized_filters.sport_category_id:
            sanitized_filters.sport_category_id = self._sanitize_search_input(sanitized_filters.sport_category_id)
        
        if sanitized_filters.position:
            sanitized_filters.position = self._sanitize_search_input(sanitized_filters.position)
        
        if sanitized_filters.location:
            sanitized_filters.location = self._sanitize_search_input(sanitized_filters.location)
        
        # Validate gender against allowed values
        if sanitized_filters.gender:
            if sanitized_filters.gender not in self.security_config.get('allowed_genders', []):
                raise InputValidationError(f"Invalid gender value: {sanitized_filters.gender}")
        
        return sanitized_filters
    
    def _get_cache_key(self, filters: AthleteSearchFilters) -> str:
        """Generate cache key for search filters"""
        filter_dict = filters.dict()
        # Remove timestamp-sensitive fields for consistent caching
        filter_dict.pop('timestamp', None)
        filter_str = str(sorted(filter_dict.items()))
        return hashlib.md5(filter_str.encode()).hexdigest()
    
    def _clean_cache(self):
        """Clean expired cache entries and maintain size limit with thread safety"""
        with self._cache_lock:
            current_time = time.time()
            expired_keys = [key for key, value in self._query_cache.items() 
                           if current_time - value['timestamp'] > self.cache_ttl]
            
            for key in expired_keys:
                del self._query_cache[key]
            
            # If still over limit, remove oldest entries
            if len(self._query_cache) > self.max_cache_size:
                sorted_items = sorted(self._query_cache.items(), 
                                    key=lambda x: x[1]['timestamp'])
                items_to_remove = len(self._query_cache) - self.max_cache_size
                for i in range(items_to_remove):
                    del self._query_cache[sorted_items[i][0]]
    
    def _log_audit_event(self, event_type: str, user_id: str = None, details: Dict[str, Any] = None):
        """Log audit events for security monitoring"""
        if not self.security_config.get('enable_audit_logging', False):
            return
        
        audit_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'user_id': user_id,
            'service': 'AthleteSearchService',
            'details': details or {}
        }
        
        logger.info(f"AUDIT: {audit_data}")
    
    def _update_query_stats(self, query_time: float):
        """Update query statistics"""
        self._query_stats['total_query_time'] += query_time
        self._query_stats['query_times'].append(query_time)
        
        # Keep only last 1000 query times to prevent memory issues
        if len(self._query_stats['query_times']) > 1000:
            self._query_stats['query_times'] = self._query_stats['query_times'][-1000:]
    
    def _calculate_average_query_time(self) -> float:
        """Calculate average query time"""
        if not self._query_stats['query_times']:
            return 0.0
        return self._query_stats['total_query_time'] / len(self._query_stats['query_times'])
    
    @PerformanceMonitor.monitor("search_athletes")
    async def search_athletes(self, filters: AthleteSearchFilters, user_id: str = None) -> PaginatedResponse:
        """Search athletes with optimized filtering, validation, and caching"""
        start_time = time.time()
        self._query_stats['total_queries'] += 1
        
        # Log audit event
        self._log_audit_event("search_athletes", user_id, {"filters": filters.dict()})
        
        try:
            # Validate and sanitize search parameters
            sanitized_filters = self._validate_and_sanitize_filters(filters)
            self._validate_search_parameters(sanitized_filters)
            
            if self.logging_config.get('log_search_queries', False):
                logger.info(f"Searching athletes with filters: {sanitized_filters}")
            
            # Check cache if enabled
            cache_key = None
            if self.performance_config.get('enable_caching', False):
                cache_key = self._get_cache_key(sanitized_filters)
                with self._cache_lock:
                    cached_result = self._query_cache.get(cache_key)
                    
                    if cached_result and time.time() - cached_result['timestamp'] < self.cache_ttl:
                        self._query_stats['cache_hits'] += 1
                        if self.logging_config.get('log_query_performance', False):
                            logger.info(f"Cache hit for search query: {cache_key}")
                        return cached_result['data']
                    
                    self._query_stats['cache_misses'] += 1
            
            # Perform search
            result = await self._perform_search(sanitized_filters)
            
            # Cache result if caching is enabled
            if self.performance_config.get('enable_caching', False) and cache_key:
                try:
                    self._clean_cache()  # Clean before adding new entry
                    with self._cache_lock:
                        self._query_cache[cache_key] = {
                            'data': result,
                            'timestamp': time.time()
                        }
                except Exception as e:
                    logger.warning(f"Failed to cache result: {e}")
                    # Continue without caching
            
            return result
            
        except ValidationError as e:
            logger.error(f"Validation error searching athletes: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"Database error searching athletes: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching athletes: {e}", exc_info=True)
            raise AthleteServiceError(f"Failed to search athletes: {str(e)}")
        finally:
            query_time = time.time() - start_time
            self._update_query_stats(query_time)
    
    @PerformanceMonitor.monitor("perform_search")
    async def _perform_search(self, filters: AthleteSearchFilters) -> PaginatedResponse:
        """Internal method to perform the actual search"""
        firestore_filters = self._build_search_filters(filters)
        
        # Optimize filters if enabled
        if self.performance_config.get('enable_query_optimization', False):
            firestore_filters = self._optimize_query_filters(firestore_filters)
        
        # Get athletes with filters
        athletes = await self.athlete_repository.query(firestore_filters, filters.limit, filters.offset)
        
        # Get total count
        total_count = await self.athlete_repository.count(firestore_filters)
        
        # Rank results by relevance
        ranked_athletes = self._rank_search_results(athletes, filters)
        
        return self._build_paginated_response(filters, total_count, ranked_athletes)
    
    @PerformanceMonitor.monitor("get_athletes_by_sport_category")
    async def get_athletes_by_sport_category(self, sport_category_id: str, limit: int = None, offset: int = 0, user_id: str = None) -> PaginatedResponse:
        """Get athletes by sport category with pagination"""
        # Log audit event
        self._log_audit_event("get_athletes_by_sport_category", user_id, {"sport_category_id": sport_category_id, "limit": limit, "offset": offset})
        
        try:
            if limit is None:
                limit = self.search_limits['default_limit']
            
            # Validate parameters
            if limit <= 0 or limit > self.search_limits['max_limit']:
                raise InputValidationError(f"Limit must be between 1 and {self.search_limits['max_limit']}")
            
            if offset < 0 or offset > self.search_limits['max_offset']:
                raise InputValidationError(f"Offset must be between 0 and {self.search_limits['max_offset']}")
            
            # Sanitize input
            sanitized_sport_id = self._sanitize_search_input(sport_category_id)
            
            filters = [
                FieldFilter("primary_sport_category_id", "==", sanitized_sport_id),
                FieldFilter("is_active", "==", True)
            ]
            
            athletes = await self.athlete_repository.query(filters, limit, offset)
            total_count = await self.athlete_repository.count(filters)
            
            # Create search filters object for pagination
            search_filters = AthleteSearchFilters(
                limit=limit,
                offset=offset,
                sport_category_id=sanitized_sport_id
            )
            
            return self._build_paginated_response(search_filters, total_count, athletes)
            
        except ValidationError as e:
            logger.error(f"Validation error getting athletes by sport category: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"Database error getting athletes by sport category: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athletes by sport category: {e}", exc_info=True)
            raise AthleteServiceError(f"Failed to get athletes by sport category: {str(e)}")
    
    @PerformanceMonitor.monitor("get_athletes_by_location")
    async def get_athletes_by_location(self, location: str, limit: int = None, offset: int = 0, user_id: str = None) -> PaginatedResponse:
        """Get athletes by location with pagination"""
        # Log audit event
        self._log_audit_event("get_athletes_by_location", user_id, {"location": location, "limit": limit, "offset": offset})
        
        try:
            if limit is None:
                limit = self.search_limits['default_limit']
            
            # Validate parameters
            if limit <= 0 or limit > self.search_limits['max_limit']:
                raise InputValidationError(f"Limit must be between 1 and {self.search_limits['max_limit']}")
            
            if offset < 0 or offset > self.search_limits['max_offset']:
                raise InputValidationError(f"Offset must be between 0 and {self.search_limits['max_offset']}")
            
            # Sanitize input
            sanitized_location = self._sanitize_search_input(location)
            
            filters = [
                FieldFilter("location", "==", sanitized_location),
                FieldFilter("is_active", "==", True)
            ]
            
            athletes = await self.athlete_repository.query(filters, limit, offset)
            total_count = await self.athlete_repository.count(filters)
            
            # Create search filters object for pagination
            search_filters = AthleteSearchFilters(
                limit=limit,
                offset=offset,
                location=sanitized_location
            )
            
            return self._build_paginated_response(search_filters, total_count, athletes)
            
        except ValidationError as e:
            logger.error(f"Validation error getting athletes by location: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"Database error getting athletes by location: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athletes by location: {e}", exc_info=True)
            raise AthleteServiceError(f"Failed to get athletes by location: {str(e)}")
    
    @PerformanceMonitor.monitor("get_athletes_by_age_range")
    async def get_athletes_by_age_range(self, min_age: int, max_age: int, limit: int = None, offset: int = 0, user_id: str = None) -> PaginatedResponse:
        """Get athletes by age range with pagination"""
        # Log audit event
        self._log_audit_event("get_athletes_by_age_range", user_id, {"min_age": min_age, "max_age": max_age, "limit": limit, "offset": offset})
        
        try:
            if limit is None:
                limit = self.search_limits['default_limit']
            
            # Validate parameters
            if min_age < self.age_limits['min_age'] or max_age > self.age_limits['max_age']:
                raise InputValidationError(f"Age must be between {self.age_limits['min_age']} and {self.age_limits['max_age']}")
            
            if min_age > max_age:
                raise InputValidationError("Minimum age cannot be greater than maximum age")
            
            if limit <= 0 or limit > self.search_limits['max_limit']:
                raise InputValidationError(f"Limit must be between 1 and {self.search_limits['max_limit']}")
            
            if offset < 0 or offset > self.search_limits['max_offset']:
                raise InputValidationError(f"Offset must be between 0 and {self.search_limits['max_offset']}")
            
            # Build age filters with corrected logic
            today = date.today()
            min_date = today - relativedelta(years=max_age)
            max_date = today - relativedelta(years=min_age)
            
            filters = [
                FieldFilter("date_of_birth", ">=", min_date.isoformat()),
                FieldFilter("date_of_birth", "<=", max_date.isoformat()),
                FieldFilter("is_active", "==", True)
            ]
            
            athletes = await self.athlete_repository.query(filters, limit, offset)
            total_count = await self.athlete_repository.count(filters)
            
            # Create search filters object for pagination
            search_filters = AthleteSearchFilters(
                limit=limit,
                offset=offset,
                min_age=min_age,
                max_age=max_age
            )
            
            return self._build_paginated_response(search_filters, total_count, athletes)
            
        except ValidationError as e:
            logger.error(f"Validation error getting athletes by age range: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"Database error getting athletes by age range: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athletes by age range: {e}", exc_info=True)
            raise AthleteServiceError(f"Failed to get athletes by age range: {str(e)}")
    
    @PerformanceMonitor.monitor("get_active_athletes_count")
    async def get_active_athletes_count(self, user_id: str = None) -> int:
        """Get total count of active athletes"""
        # Log audit event
        self._log_audit_event("get_active_athletes_count", user_id)
        
        try:
            filters = [FieldFilter("is_active", "==", True)]
            return await self.athlete_repository.count(filters)
        except ValidationError as e:
            logger.error(f"Validation error getting active athletes count: {e}")
            raise
        except DatabaseError as e:
            logger.error(f"Database error getting active athletes count: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting active athletes count: {e}", exc_info=True)
            raise AthleteServiceError(f"Failed to get active athletes count: {str(e)}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring"""
        return {
            'total_queries': self._query_stats['total_queries'],
            'cache_hits': self._query_stats['cache_hits'],
            'cache_misses': self._query_stats['cache_misses'],
            'cache_hit_rate': (self._query_stats['cache_hits'] / max(self._query_stats['total_queries'], 1)) * 100,
            'total_query_time': self._query_stats['total_query_time'],
            'avg_query_time': self._calculate_average_query_time(),
            'cache_size': len(self._query_cache),
            'max_cache_size': self.max_cache_size,
            'performance_monitor_metrics': self.performance_monitor.get_metrics()
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        return {
            'status': 'healthy',
            'cache_status': {
                'enabled': self.performance_config.get('enable_caching', False),
                'size': len(self._query_cache),
                'max_size': self.max_cache_size,
                'hit_rate': self.get_performance_stats()['cache_hit_rate']
            },
            'database_status': 'connected',  # Could check actual connection
            'performance': {
                'total_queries': self._query_stats['total_queries'],
                'avg_query_time': self._calculate_average_query_time(),
                'slow_operations': self.performance_monitor.get_slow_operations()
            },
            'security': {
                'input_validation': self.security_config.get('enable_input_validation', False),
                'sanitization': self.security_config.get('enable_sanitization', False),
                'audit_logging': self.security_config.get('enable_audit_logging', False)
            }
        }
    
    def clear_cache(self):
        """Clear the query cache"""
        with self._cache_lock:
            self._query_cache.clear()
        logger.info("Query cache cleared")
    
    # Private helper methods
    
    def _validate_search_parameters(self, filters: AthleteSearchFilters) -> None:
        """Validate search parameters"""
        if filters.limit <= 0 or filters.limit > self.search_limits['max_limit']:
            raise InputValidationError(f"Limit must be between 1 and {self.search_limits['max_limit']}")
        
        if filters.offset < 0 or filters.offset > self.search_limits['max_offset']:
            raise InputValidationError(f"Offset must be between 0 and {self.search_limits['max_offset']}")
        
        # Validate age filters
        if filters.min_age and filters.max_age and filters.min_age > filters.max_age:
            raise InputValidationError("Minimum age cannot be greater than maximum age")
        
        if filters.min_age and filters.min_age < self.age_limits['min_age']:
            raise InputValidationError(f"Minimum age cannot be less than {self.age_limits['min_age']}")
        
        if filters.max_age and filters.max_age > self.age_limits['max_age']:
            raise InputValidationError(f"Maximum age cannot exceed {self.age_limits['max_age']}")
    
    def _optimize_query_filters(self, filters: List[FieldFilter]) -> List[FieldFilter]:
        """Optimize query filters for better performance"""
        if not self.performance_config.get('enable_query_optimization', False):
            return filters
        
        # Sort filters by selectivity (most selective first)
        selectivity_order = ['is_active', 'primary_sport_category_id', 'position', 'gender', 'location']
        optimized_filters = []
        
        for field in selectivity_order:
            for filter_obj in filters:
                if hasattr(filter_obj, 'field_path') and filter_obj.field_path == field:
                    optimized_filters.append(filter_obj)
                    break
        
        # Add remaining filters
        for filter_obj in filters:
            if filter_obj not in optimized_filters:
                optimized_filters.append(filter_obj)
        
        return optimized_filters
    
    def _build_search_filters(self, filters: AthleteSearchFilters) -> List[FieldFilter]:
        """Build Firestore filters for search with input sanitization"""
        firestore_filters = []
        
        if filters.sport_category_id:
            sanitized_id = self._sanitize_search_input(filters.sport_category_id)
            firestore_filters.append(FieldFilter("primary_sport_category_id", "==", sanitized_id))
        
        if filters.position:
            sanitized_position = self._sanitize_search_input(filters.position)
            firestore_filters.append(FieldFilter("position", "==", sanitized_position))
        
        if filters.gender:
            sanitized_gender = self._sanitize_search_input(filters.gender)
            # Validate gender against allowed values
            if sanitized_gender in self.security_config.get('allowed_genders', ['male', 'female', 'other']):
                firestore_filters.append(FieldFilter("gender", "==", sanitized_gender))
            else:
                logger.warning(f"Invalid gender value: {sanitized_gender}")
        
        if filters.location:
            sanitized_location = self._sanitize_search_input(filters.location)
            firestore_filters.append(FieldFilter("location", "==", sanitized_location))
        
        # Add active filter
        firestore_filters.append(FieldFilter("is_active", "==", True))
        
        # Optimize age filtering using Firestore date queries with corrected logic
        if filters.min_age or filters.max_age:
            today = date.today()
            if filters.min_age:
                max_date = today - relativedelta(years=filters.min_age)
                firestore_filters.append(FieldFilter("date_of_birth", "<=", max_date.isoformat()))
            if filters.max_age:
                min_date = today - relativedelta(years=filters.max_age)
                firestore_filters.append(FieldFilter("date_of_birth", ">=", min_date.isoformat()))
        
        return firestore_filters
    
    def _rank_search_results(self, athletes: List[Dict[str, Any]], filters: AthleteSearchFilters) -> List[Dict[str, Any]]:
        """Rank search results by relevance"""
        if not athletes:
            return athletes
        
        for athlete in athletes:
            score = 0
            
            # Sport category match
            if filters.sport_category_id and athlete.get('primary_sport_category_id') == filters.sport_category_id:
                score += 50
            
            # Position match
            if filters.position and athlete.get('position') == filters.position:
                score += 30
            
            # Location match
            if filters.location and athlete.get('location') == filters.location:
                score += 20
            
            # Profile completion bonus
            profile_fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'location', 'position']
            completed_fields = sum(1 for field in profile_fields if athlete.get(field))
            completion_rate = completed_fields / len(profile_fields)
            score += int(completion_rate * 20)
            
            athlete['relevance_score'] = score
        
        # Sort by relevance score
        return sorted(athletes, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    def _build_paginated_response(self, filters: AthleteSearchFilters, total_count: int, athletes: List[Dict[str, Any]]) -> PaginatedResponse:
        """Build paginated response"""
        return PaginatedResponse(
            count=total_count,
            results=athletes,
            next=f"?limit={filters.limit}&offset={filters.offset + filters.limit}" if filters.offset + filters.limit < total_count else None,
            previous=f"?limit={filters.limit}&offset={max(0, filters.offset - filters.limit)}" if filters.offset > 0 else None
        ) 