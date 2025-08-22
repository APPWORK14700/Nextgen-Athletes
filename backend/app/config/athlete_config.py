"""
Configuration file for athlete services
"""
from typing import Dict, Any, List
import os

# Environment-based configuration
def get_athlete_config() -> Dict[str, Any]:
    """Get athlete service configuration from environment variables with defaults"""
    
    config = {
        # Field weights for profile completion scoring
        'field_weights': {
            "first_name": int(os.getenv('FIELD_WEIGHT_FIRST_NAME', '10')),
            "last_name": int(os.getenv('FIELD_WEIGHT_LAST_NAME', '10')),
            "date_of_birth": int(os.getenv('FIELD_WEIGHT_DATE_OF_BIRTH', '8')),
            "gender": int(os.getenv('FIELD_WEIGHT_GENDER', '8')),
            "location": int(os.getenv('FIELD_WEIGHT_LOCATION', '10')),
            "primary_sport_category_id": int(os.getenv('FIELD_WEIGHT_PRIMARY_SPORT', '12')),
            "position": int(os.getenv('FIELD_WEIGHT_POSITION', '12')),
            "height_cm": int(os.getenv('FIELD_WEIGHT_HEIGHT', '8')),
            "weight_kg": int(os.getenv('FIELD_WEIGHT_WEIGHT', '8')),
            "academic_info": int(os.getenv('FIELD_WEIGHT_ACADEMIC', '6')),
            "career_highlights": int(os.getenv('FIELD_WEIGHT_CAREER', '8')),
            "profile_image_url": int(os.getenv('FIELD_WEIGHT_PROFILE_IMAGE', '10'))
        },
        
        # Field categories for organization
        'field_categories': {
            "basic_info": ["first_name", "last_name", "date_of_birth", "gender"],
            "sport_info": ["primary_sport_category_id", "position", "secondary_sport_category_ids"],
            "physical_info": ["height_cm", "weight_kg", "location"],
            "additional_info": ["academic_info", "career_highlights", "profile_image_url"]
        },
        
        # Search and pagination limits
        'search_limits': {
            'min_limit': int(os.getenv('ATHLETE_MIN_SEARCH_LIMIT', '1')),
            'max_limit': int(os.getenv('ATHLETE_MAX_SEARCH_LIMIT', '100')),
            'default_limit': int(os.getenv('ATHLETE_DEFAULT_SEARCH_LIMIT', '20')),
            'max_offset': int(os.getenv('ATHLETE_MAX_OFFSET', '10000'))
        },
        
        # Age validation limits
        'age_limits': {
            'min_age': int(os.getenv('ATHLETE_MIN_AGE', '13')),
            'max_age': int(os.getenv('ATHLETE_MAX_AGE', '100')),
            'junior_max': int(os.getenv('ATHLETE_JUNIOR_MAX_AGE', '18')),
            'intermediate_max': int(os.getenv('ATHLETE_INTERMEDIATE_MAX_AGE', '22')),
            'senior_max': int(os.getenv('ATHLETE_SENIOR_MAX_AGE', '30')),
            'veteran_min': int(os.getenv('ATHLETE_VETERAN_MIN_AGE', '31'))
        },
        
        # Bulk operation limits
        'bulk_limits': {
            'max_bulk_update': int(os.getenv('ATHLETE_MAX_BULK_UPDATE', '500')),
            'batch_size': int(os.getenv('ATHLETE_BATCH_SIZE', '50')),
            'max_concurrent_batches': int(os.getenv('ATHLETE_MAX_CONCURRENT_BATCHES', '10'))
        },
        
        # Recommendation scoring weights
        'recommendation_weights': {
            'sport_category_match': int(os.getenv('RECOMMENDATION_SPORT_MATCH', '50')),
            'position_match': int(os.getenv('RECOMMENDATION_POSITION_MATCH', '30')),
            'location_match': int(os.getenv('RECOMMENDATION_LOCATION_MATCH', '20')),
            'profile_completion': float(os.getenv('RECOMMENDATION_PROFILE_COMPLETION', '0.3')),
            'recent_activity_bonus': int(os.getenv('RECOMMENDATION_ACTIVITY_BONUS', '10')),
            'recent_activity_days': int(os.getenv('RECOMMENDATION_ACTIVITY_DAYS', '30')),
            # Similarity scoring weights
            'age_similarity_close': int(os.getenv('RECOMMENDATION_AGE_SIMILARITY_CLOSE', '25')),
            'age_similarity_medium': int(os.getenv('RECOMMENDATION_AGE_SIMILARITY_MEDIUM', '15')),
            'age_similarity_far': int(os.getenv('RECOMMENDATION_AGE_SIMILARITY_FAR', '5')),
            'completion_similarity_close': int(os.getenv('RECOMMENDATION_COMPLETION_SIMILARITY_CLOSE', '20')),
            'completion_similarity_medium': int(os.getenv('RECOMMENDATION_COMPLETION_SIMILARITY_MEDIUM', '10'))
        },
        
        # Experience scoring thresholds
        'experience_thresholds': {
            'extensive_experience': int(os.getenv('EXPERIENCE_EXTENSIVE_THRESHOLD', '500')),
            'moderate_experience': int(os.getenv('EXPERIENCE_MODERATE_THRESHOLD', '200')),
            'min_experience': int(os.getenv('EXPERIENCE_MIN_THRESHOLD', '50')),
            'extensive_score': int(os.getenv('EXPERIENCE_EXTENSIVE_SCORE', '20')),
            'moderate_score': int(os.getenv('EXPERIENCE_MODERATE_SCORE', '15')),
            'min_score': int(os.getenv('EXPERIENCE_MIN_SCORE', '10')),
            'age_bonus': int(os.getenv('EXPERIENCE_AGE_BONUS', '15'))
        },
        
        # Statistics sampling limits
        'statistics_limits': {
            'max_sample_size': int(os.getenv('STATS_MAX_SAMPLE_SIZE', '1000')),
            'cache_ttl_seconds': int(os.getenv('STATS_CACHE_TTL', '3600')),
            'max_age_groups': int(os.getenv('STATS_MAX_AGE_GROUPS', '10'))
        },
        
        # Collection names for consistency
        'collections': {
            "athlete_profiles": "athlete_profiles",
            "users": "users",
            "media": "media",
            "stats_achievements": "stats_achievements",
            "user_profiles": "user_profiles",
            "sport_categories": "sport_categories",
            "profile_views": "profile_views",
            "messages": "messages",
            "opportunity_applications": "opportunity_applications",
            "scout_preferences": "scout_preferences"
        },
        
        # Performance settings
        'performance': {
            'enable_caching': os.getenv('ATHLETE_ENABLE_CACHING', 'true').lower() == 'true',
            'cache_size': int(os.getenv('ATHLETE_CACHE_SIZE', '128')),
            'cache_ttl_seconds': int(os.getenv('ATHLETE_CACHE_TTL_SECONDS', '3600')),
            'enable_batch_processing': os.getenv('ATHLETE_ENABLE_BATCH_PROCESSING', 'true').lower() == 'true',
            'max_concurrent_queries': int(os.getenv('ATHLETE_MAX_CONCURRENT_QUERIES', '5')),
            'enable_query_optimization': os.getenv('ATHLETE_ENABLE_QUERY_OPTIMIZATION', 'true').lower() == 'true',
            'max_query_timeout': int(os.getenv('ATHLETE_MAX_QUERY_TIMEOUT', '30'))
        },
        
        # Logging settings
        'logging': {
            'log_level': os.getenv('ATHLETE_LOG_LEVEL', 'INFO'),
            'log_profile_updates': os.getenv('ATHLETE_LOG_PROFILE_UPATES', 'true').lower() == 'true',
            'log_search_queries': os.getenv('ATHLETE_LOG_SEARCH_QUERIES', 'false').lower() == 'true',
            'log_query_performance': os.getenv('ATHLETE_LOG_QUERY_PERFORMANCE', 'false').lower() == 'true',
            'slow_query_threshold': float(os.getenv('ATHLETE_SLOW_QUERY_THRESHOLD', '1.0')),
            'slow_count_query_threshold': float(os.getenv('ATHLETE_SLOW_COUNT_QUERY_THRESHOLD', '0.5')),
            'log_cache_operations': os.getenv('ATHLETE_LOG_CACHE_OPERATIONS', 'false').lower() == 'true'
        },
        
        # Security settings
        'security': {
            'enable_input_validation': os.getenv('ATHLETE_ENABLE_INPUT_VALIDATION', 'true').lower() == 'true',
            'enable_sanitization': os.getenv('ATHLETE_ENABLE_SANITIZATION', 'true').lower() == 'true',
            'max_string_length': int(os.getenv('ATHLETE_MAX_STRING_LENGTH', '1000')),
            'allowed_genders': os.getenv('ATHLETE_ALLOWED_GENDERS', 'male,female,other').split(','),
            'enable_rate_limiting': os.getenv('ATHLETE_ENABLE_RATE_LIMITING', 'true').lower() == 'true',
            'max_requests_per_minute': int(os.getenv('ATHLETE_MAX_REQUESTS_PER_MINUTE', '100')),
            'blocked_patterns': os.getenv('ATHLETE_BLOCKED_PATTERNS', 'script,<,>,javascript').split(','),
            'enable_audit_logging': os.getenv('ATHLETE_ENABLE_AUDIT_LOGGING', 'true').lower() == 'true'
        }
    }
    
    return config

# Development configuration
DEV_CONFIG = {
    'field_weights': {
        "first_name": 10, "last_name": 10, "date_of_birth": 8,
        "gender": 8, "location": 10, "primary_sport_category_id": 12,
        "position": 12, "height_cm": 8, "weight_kg": 8,
        "academic_info": 6, "career_highlights": 8, "profile_image_url": 10
    },
    'search_limits': {'min_limit': 1, 'max_limit': 200, 'default_limit': 20, 'max_offset': 10000},
    'age_limits': {'min_age': 13, 'max_age': 100, 'junior_max': 18, 'intermediate_max': 22, 'senior_max': 30, 'veteran_min': 31},
    'bulk_limits': {'max_bulk_update': 1000, 'batch_size': 100, 'max_concurrent_batches': 20},
    'recommendation_weights': {
        'sport_category_match': 50, 'position_match': 30, 'location_match': 20,
        'profile_completion': 0.3, 'recent_activity_bonus': 10, 'recent_activity_days': 30,
        'age_similarity_close': 25, 'age_similarity_medium': 15, 'age_similarity_far': 5,
        'completion_similarity_close': 20, 'completion_similarity_medium': 10
    },
    'experience_thresholds': {
        'extensive_experience': 500, 'moderate_experience': 200, 'min_experience': 50,
        'extensive_score': 20, 'moderate_score': 15, 'min_score': 10, 'age_bonus': 15
    },
    'statistics_limits': {'max_sample_size': 2000, 'cache_ttl_seconds': 1800, 'max_age_groups': 15},
    'performance': {'enable_caching': True, 'cache_size': 256, 'enable_batch_processing': True, 'max_concurrent_queries': 10},
    'logging': {'log_level': 'DEBUG', 'log_profile_updates': True, 'log_search_queries': True, 'log_query_performance': True, 'slow_query_threshold': 1.0, 'slow_count_query_threshold': 0.5},
    'security': {'enable_input_validation': True, 'enable_sanitization': True, 'max_string_length': 2000, 'allowed_genders': ['male', 'female', 'other']}
}

# Production configuration
PROD_CONFIG = {
    'field_weights': {
        "first_name": 10, "last_name": 10, "date_of_birth": 8,
        "gender": 8, "location": 10, "primary_sport_category_id": 12,
        "position": 12, "height_cm": 8, "weight_kg": 8,
        "academic_info": 6, "career_highlights": 8, "profile_image_url": 10
    },
    'search_limits': {'min_limit': 1, 'max_limit': 100, 'default_limit': 20, 'max_offset': 5000},
    'age_limits': {'min_age': 13, 'max_age': 100, 'junior_max': 18, 'intermediate_max': 22, 'senior_max': 30, 'veteran_min': 31},
    'bulk_limits': {'max_bulk_update': 500, 'batch_size': 50, 'max_concurrent_batches': 10},
    'recommendation_weights': {
        'sport_category_match': 50, 'position_match': 30, 'location_match': 20,
        'profile_completion': 0.3, 'recent_activity_bonus': 10, 'recent_activity_days': 30,
        'age_similarity_close': 25, 'age_similarity_medium': 15, 'age_similarity_far': 5,
        'completion_similarity_close': 20, 'completion_similarity_medium': 10
    },
    'experience_thresholds': {
        'extensive_experience': 500, 'moderate_experience': 200, 'min_experience': 50,
        'extensive_score': 20, 'moderate_score': 15, 'min_score': 10, 'age_bonus': 15
    },
    'statistics_limits': {'max_sample_size': 1000, 'cache_ttl_seconds': 3600, 'max_age_groups': 10},
    'performance': {'enable_caching': True, 'cache_size': 128, 'enable_batch_processing': True, 'max_concurrent_queries': 5},
    'logging': {'log_level': 'INFO', 'log_profile_updates': True, 'log_search_queries': False, 'log_query_performance': False, 'slow_query_threshold': 1.0, 'slow_count_query_threshold': 0.5},
    'security': {'enable_input_validation': True, 'enable_sanitization': True, 'max_string_length': 1000, 'allowed_genders': ['male', 'female', 'other']}
}

# Get configuration based on environment
def get_config(environment: str = None) -> Dict[str, Any]:
    """Get configuration for specific environment"""
    if environment == 'dev':
        return DEV_CONFIG
    elif environment == 'prod':
        return PROD_CONFIG
    else:
        return get_athlete_config() 