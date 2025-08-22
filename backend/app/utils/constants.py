"""
Constants and configuration values for the application
"""
from datetime import timedelta

# Cache Configuration
CACHE_CONFIG = {
    "MAX_SIZE": 1000,
    "TTL_MINUTES": 15,
    "CLEANUP_INTERVAL_MINUTES": 30,
    "MAX_ENTRIES_TO_REMOVE": 200,  # 20% of max size
}

# Rate Limiting Configuration
RATE_LIMIT_CONFIG = {
    "LOGIN": {
        "max_requests": 5,
        "window_seconds": 300,  # 5 minutes
        "block_duration_seconds": 300,  # 5 minutes
    },
    "REGISTER": {
        "max_requests": 3,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 1800,  # 30 minutes
    },
    "PASSWORD_RESET": {
        "max_requests": 3,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 1800,  # 30 minutes
    },
    "SEARCH": {
        "max_requests": 100,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 300,  # 5 minutes
    },
    "REPORT": {
        "max_requests": 5,
        "window_seconds": 86400,  # 24 hours
        "block_duration_seconds": 3600,  # 1 hour
    },
    "BLOCK": {
        "max_requests": 10,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 1800,  # 30 minutes
    },
    "PROFILE_UPDATE": {
        "max_requests": 20,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 300,  # 5 minutes
    },
    "MEDIA_UPLOAD": {
        "max_requests": 50,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 600,  # 10 minutes
    },
    "MESSAGE": {
        "max_requests": 100,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 300,  # 5 minutes
    },
    "API_CALL": {
        "max_requests": 1000,
        "window_seconds": 3600,  # 1 hour
        "block_duration_seconds": 300,  # 5 minutes
    },
}

# User Validation Constants
USER_VALIDATION = {
    "USERNAME": {
        "MIN_LENGTH": 3,
        "MAX_LENGTH": 30,
        "PATTERN": r'^[a-zA-Z0-9_-]+$',
    },
    "EMAIL": {
        "MAX_LENGTH": 254,
        "PATTERN": r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    },
    "PHONE": {
        "MIN_LENGTH": 10,
        "MAX_LENGTH": 15,
        "PATTERN": r'^\+?[1-9]\d{1,14}$',
    },
    "PASSWORD": {
        "MIN_LENGTH": 8,
        "MAX_LENGTH": 128,
        "REQUIRE_UPPERCASE": True,
        "REQUIRE_LOWERCASE": True,
        "REQUIRE_DIGIT": True,
        "REQUIRE_SPECIAL": True,
    },
    "TEXT_FIELDS": {
        "BIO_MAX_LENGTH": 1000,
        "REASON_MAX_LENGTH": 500,
        "DESCRIPTION_MAX_LENGTH": 1000,
        "SEARCH_QUERY_MAX_LENGTH": 100,
    },
}

# Pagination Constants
PAGINATION = {
    "DEFAULT_LIMIT": 100,
    "MAX_LIMIT": 1000,
    "MIN_LIMIT": 1,
    "DEFAULT_OFFSET": 0,
    "MIN_OFFSET": 0,
}

# Role and Permission Constants
ROLES = {
    "ATHLETE": "athlete",
    "SCOUT": "scout",
    "ADMIN": "admin",
}

ROLE_HIERARCHY = {
    "admin": 3,
    "scout": 2,
    "athlete": 1,
}

USER_STATUSES = {
    "ACTIVE": "active",
    "SUSPENDED": "suspended",
    "DELETED": "deleted",
    "PENDING": "pending",
    "VERIFIED": "verified",
}

# Database Constants
DATABASE = {
    "MAX_BATCH_SIZE": 500,
    "QUERY_TIMEOUT_SECONDS": 30,
    "RETRY_ATTEMPTS": 3,
    "RETRY_DELAY_SECONDS": 1,
}

# Security Constants
SECURITY = {
    "PASSWORD_HASH_ROUNDS": 12,
    "JWT_EXPIRY_HOURS": 24,
    "REFRESH_TOKEN_EXPIRY_DAYS": 30,
    "MAX_LOGIN_ATTEMPTS": 5,
    "LOCKOUT_DURATION_MINUTES": 15,
    "SESSION_TIMEOUT_MINUTES": 60,
}

# File Upload Constants
FILE_UPLOAD = {
    "MAX_FILE_SIZE_MB": 50,
    "ALLOWED_IMAGE_TYPES": ["image/jpeg", "image/png", "image/gif", "image/webp"],
    "ALLOWED_VIDEO_TYPES": ["video/mp4", "video/avi", "video/mov", "video/wmv"],
    "ALLOWED_DOCUMENT_TYPES": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "MAX_FILES_PER_UPLOAD": 10,
}

# Notification Constants
NOTIFICATION = {
    "MAX_TITLE_LENGTH": 100,
    "MAX_MESSAGE_LENGTH": 500,
    "MAX_PRIORITY": 5,
    "DEFAULT_PRIORITY": 3,
    "BATCH_SIZE": 100,
    "RETENTION_DAYS": 90,
}

# Search Constants
SEARCH = {
    "MAX_QUERY_LENGTH": 100,
    "MIN_QUERY_LENGTH": 2,
    "MAX_RESULTS": 1000,
    "DEFAULT_RESULTS": 100,
    "FUZZY_MATCH_THRESHOLD": 0.8,
}

# Performance Monitoring Constants
PERFORMANCE = {
    "SLOW_OPERATION_THRESHOLD_MS": 1000,
    "METRICS_RETENTION_HOURS": 24,
    "CLEANUP_INTERVAL_MINUTES": 60,
    "MAX_METRIC_VALUES": 1000,
}

# Error Messages
ERROR_MESSAGES = {
    "VALIDATION": {
        "REQUIRED_FIELD": "{field} is required",
        "INVALID_FORMAT": "Invalid {field} format",
        "TOO_SHORT": "{field} must be at least {min_length} characters long",
        "TOO_LONG": "{field} cannot exceed {max_length} characters",
        "INVALID_CHARACTERS": "{field} contains invalid characters",
        "ALREADY_EXISTS": "{field} already exists",
        "NOT_FOUND": "{field} not found",
    },
    "RATE_LIMIT": {
        "EXCEEDED": "Rate limit exceeded for {operation}. Please try again later.",
        "BLOCKED": "Your account has been temporarily blocked due to excessive requests.",
        "RETRY_AFTER": "Please try again after {seconds} seconds.",
    },
    "PERMISSION": {
        "INSUFFICIENT": "Insufficient permissions. Required: {required}, Current: {current}",
        "UNAUTHORIZED": "You are not authorized to perform this action",
        "FORBIDDEN": "Access denied",
    },
    "DATABASE": {
        "CONNECTION_FAILED": "Database connection failed",
        "QUERY_TIMEOUT": "Database query timed out",
        "TRANSACTION_FAILED": "Database transaction failed",
    },
}

# Success Messages
SUCCESS_MESSAGES = {
    "USER": {
        "CREATED": "User created successfully",
        "UPDATED": "User updated successfully",
        "DELETED": "User deleted successfully",
        "VERIFIED": "User verified successfully",
        "BLOCKED": "User blocked successfully",
        "UNBLOCKED": "User unblocked successfully",
        "REPORTED": "User reported successfully",
    },
    "PROFILE": {
        "UPDATED": "Profile updated successfully",
        "COMPLETION_UPDATED": "Profile completion updated successfully",
    },
    "SETTINGS": {
        "UPDATED": "Settings updated successfully",
    },
}

# HTTP Status Codes
HTTP_STATUS = {
    "OK": 200,
    "CREATED": 201,
    "NO_CONTENT": 204,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "TOO_MANY_REQUESTS": 429,
    "INTERNAL_SERVER_ERROR": 500,
    "SERVICE_UNAVAILABLE": 503,
}

# Time Constants
TIME = {
    "SECONDS_IN_MINUTE": 60,
    "SECONDS_IN_HOUR": 3600,
    "SECONDS_IN_DAY": 86400,
    "MINUTES_IN_HOUR": 60,
    "HOURS_IN_DAY": 24,
    "DAYS_IN_WEEK": 7,
    "DAYS_IN_MONTH": 30,
    "DAYS_IN_YEAR": 365,
}

# Cache Keys
CACHE_KEYS = {
    "USER_PROFILE": "user_profile:{user_id}",
    "USER_SETTINGS": "user_settings:{user_id}",
    "USER_ANALYTICS": "user_analytics:{user_id}",
    "USER_SEARCH": "user_search:{query_hash}",
    "RATE_LIMIT": "rate_limit:{operation}:{key}",
    "METRICS": "metrics:{metric_name}",
}

# Logging Constants
LOGGING = {
    "LEVELS": {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    },
    "FORMATS": {
        "DEFAULT": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "DETAILED": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        "JSON": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    },
    "MAX_FILE_SIZE_MB": 100,
    "BACKUP_COUNT": 5,
}

# API Constants
API = {
    "VERSION": "v1",
    "PREFIX": "/api/v1",
    "MAX_REQUEST_SIZE_MB": 100,
    "REQUEST_TIMEOUT_SECONDS": 30,
    "CORS_ORIGINS": ["*"],  # Configure appropriately for production
    "CORS_METHODS": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    "CORS_HEADERS": ["Content-Type", "Authorization", "X-Requested-With"],
}

# Environment Constants
ENVIRONMENT = {
    "DEVELOPMENT": "development",
    "STAGING": "staging",
    "PRODUCTION": "production",
    "TESTING": "testing",
}

# Feature Flags
FEATURE_FLAGS = {
    "ENABLE_CACHING": True,
    "ENABLE_RATE_LIMITING": True,
    "ENABLE_METRICS": True,
    "ENABLE_PERFORMANCE_MONITORING": True,
    "ENABLE_AUDIT_LOGGING": True,
    "ENABLE_BACKUP": True,
    "ENABLE_ANALYTICS": True,
}

# Backup Constants
BACKUP = {
    "ENABLED": True,
    "INTERVAL_HOURS": 24,
    "RETENTION_DAYS": 30,
    "MAX_BACKUP_SIZE_MB": 1000,
    "COMPRESSION_ENABLED": True,
    "ENCRYPTION_ENABLED": True,
}

# Monitoring Constants
MONITORING = {
    "HEALTH_CHECK_INTERVAL_SECONDS": 60,
    "METRICS_COLLECTION_INTERVAL_SECONDS": 300,
    "ALERT_THRESHOLD_PERCENTAGE": 80,
    "MAX_LOG_ENTRIES": 10000,
    "LOG_ROTATION_SIZE_MB": 100,
} 