"""
Configuration file for notification service
"""
from typing import Dict, Any
import os

# Environment-based configuration
def get_notification_config() -> Dict[str, Any]:
    """Get notification service configuration from environment variables with defaults"""
    
    config = {
        # Notification limits
        'max_notifications_per_user': int(os.getenv('MAX_NOTIFICATIONS_PER_USER', '1000')),
        'rate_limit_window': int(os.getenv('RATE_LIMIT_WINDOW', '3600')),  # 1 hour in seconds
        'rate_limit_max': int(os.getenv('RATE_LIMIT_MAX', '50')),  # Max notifications per hour per user
        
        # Cleanup settings
        'cleanup_days_old': int(os.getenv('CLEANUP_DAYS_OLD', '30')),
        
        # Batch operation settings
        'batch_size': int(os.getenv('BATCH_SIZE', '500')),  # Firestore batch limit
        
        # Performance settings
        'enable_metrics': os.getenv('ENABLE_METRICS', 'true').lower() == 'true',
        'enable_performance_monitoring': os.getenv('ENABLE_PERFORMANCE_MONITORING', 'false').lower() == 'true',
        
        # Logging settings
        'log_level': os.getenv('NOTIFICATION_LOG_LEVEL', 'INFO'),
        'log_metrics': os.getenv('LOG_METRICS', 'false').lower() == 'true',
        
        # Template settings
        'enable_templates': os.getenv('ENABLE_TEMPLATES', 'true').lower() == 'true',
        'custom_templates': os.getenv('CUSTOM_TEMPLATES', '{}'),  # JSON string for custom templates
        
        # Monitoring settings
        'enable_performance_monitoring': os.getenv('ENABLE_PERFORMANCE_MONITORING', 'false').lower() == 'true',
        'performance_threshold_ms': int(os.getenv('PERFORMANCE_THRESHOLD_MS', '1000')),
    }
    
    return config

# Development configuration
DEV_CONFIG = {
    'max_notifications_per_user': 500,
    'rate_limit_window': 1800,  # 30 minutes for faster testing
    'rate_limit_max': 100,
    'cleanup_days_old': 7,
    'batch_size': 100,
    'enable_metrics': True,
    'enable_performance_monitoring': False,  # Disabled by default in dev
    'log_level': 'DEBUG',
    'log_metrics': True,
    'enable_templates': True,
    'enable_performance_monitoring': False,
    'performance_threshold_ms': 500,
}

# Production configuration
PROD_CONFIG = {
    'max_notifications_per_user': 2000,
    'rate_limit_window': 3600,  # 1 hour
    'rate_limit_max': 30,  # More restrictive in production
    'cleanup_days_old': 90,  # Keep notifications longer in production
    'batch_size': 500,
    'enable_metrics': True,
    'enable_performance_monitoring': False,  # Disabled by default in production
    'log_level': 'WARNING',
    'log_metrics': False,
    'enable_templates': True,
    'enable_performance_monitoring': False,
    'performance_threshold_ms': 2000,
}

# Testing configuration
TEST_CONFIG = {
    'max_notifications_per_user': 100,
    'rate_limit_window': 60,  # 1 minute for fast testing
    'rate_limit_max': 1000,
    'cleanup_days_old': 1,
    'batch_size': 10,
    'enable_metrics': True,
    'enable_performance_monitoring': False,  # Disabled for testing
    'log_level': 'DEBUG',
    'log_metrics': True,
    'enable_templates': True,
    'enable_performance_monitoring': False,
    'performance_threshold_ms': 100,
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