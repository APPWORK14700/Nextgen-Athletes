"""
Configuration file for media service
"""
from typing import Dict, Any
import os

# Environment-based configuration
def get_media_config() -> Dict[str, Any]:
    """Get media service configuration from environment variables with defaults"""
    
    config = {
        # Upload limits
        'max_uploads_per_hour': int(os.getenv('MAX_UPLOADS_PER_HOUR', '20')),
        'max_file_size_mb': int(os.getenv('MAX_FILE_SIZE_MB', '100')),
        'max_bulk_upload_files': int(os.getenv('MAX_BULK_UPLOAD_FILES', '10')),
        'max_bulk_delete_files': int(os.getenv('MAX_BULK_DELETE_FILES', '50')),
        
        # Media query limits
        'default_media_limit': int(os.getenv('DEFAULT_MEDIA_LIMIT', '100')),
        'max_media_limit': int(os.getenv('MAX_MEDIA_LIMIT', '1000')),
        'default_recommendation_limit': int(os.getenv('DEFAULT_RECOMMENDATION_LIMIT', '20')),
        'max_recommendation_limit': int(os.getenv('MAX_RECOMMENDATION_LIMIT', '100')),
        'default_search_limit': int(os.getenv('DEFAULT_SEARCH_LIMIT', '50')),
        'max_search_limit': int(os.getenv('MAX_SEARCH_LIMIT', '200')),
        
        # Supported media types and formats
        'supported_types': os.getenv('SUPPORTED_MEDIA_TYPES', 'video,image,reel').split(','),
        'supported_formats': {
            'video': os.getenv('SUPPORTED_VIDEO_FORMATS', 'mp4,mov,avi').split(','),
            'image': os.getenv('SUPPORTED_IMAGE_FORMATS', 'jpg,jpeg,png,gif').split(','),
            'reel': os.getenv('SUPPORTED_REEL_FORMATS', 'mp4,mov').split(','),
        },
        
        # AI Analysis settings
        'ai_analysis_max_retries': int(os.getenv('AI_ANALYSIS_MAX_RETRIES', '5')),
        'ai_analysis_retry_delay_base_seconds': int(os.getenv('AI_ANALYSIS_RETRY_DELAY_BASE', '30')),
        'ai_analysis_max_delay_seconds': int(os.getenv('AI_ANALYSIS_MAX_DELAY', '300')),
        
        # Rate limiting
        'rate_limit_window_hours': int(os.getenv('RATE_LIMIT_WINDOW_HOURS', '1')),
        
        # Performance settings
        'enable_concurrent_uploads': os.getenv('ENABLE_CONCURRENT_UPLOADS', 'true').lower() == 'true',
        'max_concurrent_uploads': int(os.getenv('MAX_CONCURRENT_UPLOADS', '5')),
        
        # Logging settings
        'log_level': os.getenv('MEDIA_LOG_LEVEL', 'INFO'),
        'log_upload_details': os.getenv('LOG_UPLOAD_DETAILS', 'false').lower() == 'true',
        
        # Security settings
        'enable_url_validation': os.getenv('ENABLE_URL_VALIDATION', 'true').lower() == 'true',
        'allowed_url_schemes': os.getenv('ALLOWED_URL_SCHEMES', 'http,https,gs').split(','),
        'min_url_length': int(os.getenv('MIN_URL_LENGTH', '10')),
    }
    
    return config

# Development configuration
DEV_CONFIG = {
    'max_uploads_per_hour': 50,
    'max_file_size_mb': 200,
    'max_bulk_upload_files': 20,
    'max_bulk_delete_files': 100,
    'default_media_limit': 100,
    'max_media_limit': 1000,
    'default_recommendation_limit': 20,
    'max_recommendation_limit': 100,
    'default_search_limit': 50,
    'max_search_limit': 200,
    'ai_analysis_max_retries': 3,
    'ai_analysis_retry_delay_base_seconds': 10,
    'ai_analysis_max_delay_seconds': 60,
    'rate_limit_window_hours': 1,
    'enable_concurrent_uploads': True,
    'max_concurrent_uploads': 10,
    'log_level': 'DEBUG',
    'log_upload_details': True,
    'enable_url_validation': True,
    'allowed_url_schemes': ['http', 'https', 'gs'],
    'min_url_length': 10,
}

# Production configuration
PROD_CONFIG = {
    'max_uploads_per_hour': 20,
    'max_file_size_mb': 100,
    'max_bulk_upload_files': 10,
    'max_bulk_delete_files': 50,
    'default_media_limit': 100,
    'max_media_limit': 1000,
    'default_recommendation_limit': 20,
    'max_recommendation_limit': 100,
    'default_search_limit': 50,
    'max_search_limit': 200,
    'ai_analysis_max_retries': 5,
    'ai_analysis_retry_delay_base_seconds': 30,
    'ai_analysis_max_delay_seconds': 300,
    'rate_limit_window_hours': 1,
    'enable_concurrent_uploads': True,
    'max_concurrent_uploads': 5,
    'log_level': 'WARNING',
    'log_upload_details': False,
    'enable_url_validation': True,
    'allowed_url_schemes': ['https', 'gs'],
    'min_url_length': 10,
}

# Testing configuration
TEST_CONFIG = {
    'max_uploads_per_hour': 1000,
    'max_file_size_mb': 500,
    'max_bulk_upload_files': 50,
    'max_bulk_delete_files': 200,
    'default_media_limit': 100,
    'max_media_limit': 1000,
    'default_recommendation_limit': 20,
    'max_recommendation_limit': 100,
    'default_search_limit': 50,
    'max_search_limit': 200,
    'ai_analysis_max_retries': 2,
    'ai_analysis_retry_delay_base_seconds': 1,
    'ai_analysis_max_delay_seconds': 10,
    'rate_limit_window_hours': 1,
    'enable_concurrent_uploads': False,
    'max_concurrent_uploads': 1,
    'log_level': 'DEBUG',
    'log_upload_details': True,
    'enable_url_validation': True,
    'allowed_url_schemes': ['http', 'https', 'gs'],
    'min_url_length': 5,
}

def get_config_for_environment(environment: str = None) -> Dict[str, Any]:
    """Get configuration for specific environment"""
    if not environment:
        environment = os.getenv('ENVIRONMENT', 'development').lower()
    
    configs = {
        'development': DEV_CONFIG,
        'dev': DEV_CONFIG,
        'production': PROD_CONFIG,
        'prod': PROD_CONFIG,
        'testing': TEST_CONFIG,
        'test': TEST_CONFIG,
    }
    
    return configs.get(environment, DEV_CONFIG)

# Default configuration
DEFAULT_CONFIG = get_media_config() 