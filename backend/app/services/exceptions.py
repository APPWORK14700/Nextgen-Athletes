"""
Custom exceptions for athlete services with enhanced functionality
"""
from typing import Optional, Dict, Any, List, Union
import logging
from datetime import datetime, timezone
from enum import Enum
import re
import os


logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Enumeration of error codes for consistent error handling"""
    # Base errors
    ATHLETE_SERVICE_ERROR = "ATHLETE_SERVICE_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    
    # Profile and validation errors
    PROFILE_COMPLETION_ERROR = "PROFILE_COMPLETION_ERROR"
    ATHLETE_VALIDATION_ERROR = "ATHLETE_VALIDATION_ERROR"
    ATHLETE_NOT_FOUND = "ATHLETE_NOT_FOUND"
    INPUT_VALIDATION_ERROR = "INPUT_VALIDATION_ERROR"
    
    # Sport and category errors
    SPORT_CATEGORY_ERROR = "SPORT_CATEGORY_ERROR"
    
    # Operation errors
    BULK_OPERATION_ERROR = "BULK_OPERATION_ERROR"
    RECOMMENDATION_ERROR = "RECOMMENDATION_ERROR"
    STATISTICS_ERROR = "STATISTICS_ERROR"
    
    # Data and security errors
    DATA_SANITIZATION_ERROR = "DATA_SANITIZATION_ERROR"
    
    # Authentication and authorization errors
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_ERROR = "RATE_LIMIT_ERROR"
    
    # Database and connection errors
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    
    # Media and file handling errors
    MEDIA_UPLOAD_ERROR = "MEDIA_UPLOAD_ERROR"
    MEDIA_PROCESSING_ERROR = "MEDIA_PROCESSING_ERROR"
    FILE_SIZE_ERROR = "FILE_SIZE_ERROR"
    FILE_TYPE_ERROR = "FILE_TYPE_ERROR"


class DetailMixin:
    """Mixin for common detail-adding functionality across exceptions"""
    
    def add_detail(self, key: str, value: Any) -> None:
        """Add additional detail to the exception"""
        if not hasattr(self, 'details'):
            self.details = {}
        self.details[key] = value
    
    def add_details(self, details_dict: Dict[str, Any]) -> None:
        """Add multiple details at once"""
        if not hasattr(self, 'details'):
            self.details = {}
        self.details.update(details_dict)
    
    def get_detail(self, key: str, default: Any = None) -> Any:
        """Get a specific detail value"""
        return getattr(self, 'details', {}).get(key, default)
    
    def get_sanitized_message(self, include_details: bool = False) -> str:
        """Get sanitized error message for production use
        
        Args:
            include_details: Whether to include safe details in the message
            
        Returns:
            Sanitized error message safe for user consumption
        """
        # Check if we're in production mode
        is_production = os.getenv('ENVIRONMENT', 'development').lower() == 'production'
        
        if is_production:
            # In production, only show generic messages
            base_message = self._get_generic_message()
            
            if include_details and hasattr(self, 'details'):
                # Only include safe details (no sensitive information)
                safe_details = {}
                for key, value in self.details.items():
                    if key in ['field', 'operation', 'resource_type']:
                        safe_details[key] = value
                
                if safe_details:
                    detail_str = ', '.join([f"{k}: {v}" for k, v in safe_details.items()])
                    return f"{base_message} ({detail_str})"
            
            return base_message
        else:
            # In development, show full message
            return self.message
    
    def _get_generic_message(self) -> str:
        """Get generic error message based on error code"""
        if hasattr(self, 'error_code') and self.error_code:
            error_code = self.error_code.value if isinstance(self.error_code, ErrorCode) else str(self.error_code)
            
            generic_messages = {
                'ATHLETE_SERVICE_ERROR': 'An error occurred while processing your request',
                'PROFILE_COMPLETION_ERROR': 'Unable to complete profile operation',
                'ATHLETE_VALIDATION_ERROR': 'Profile validation failed',
                'ATHLETE_NOT_FOUND': 'Athlete profile not found',
                'INPUT_VALIDATION_ERROR': 'Invalid input provided',
                'SPORT_CATEGORY_ERROR': 'Sport category error',
                'BULK_OPERATION_ERROR': 'Bulk operation failed',
                'RECOMMENDATION_ERROR': 'Unable to generate recommendations',
                'STATISTICS_ERROR': 'Unable to retrieve statistics',
                'DATA_SANITIZATION_ERROR': 'Data validation failed',
                'AUTHENTICATION_ERROR': 'Authentication failed',
                'AUTHORIZATION_ERROR': 'Access denied',
                'RATE_LIMIT_ERROR': 'Too many requests',
                'DATABASE_CONNECTION_ERROR': 'Service temporarily unavailable',
                'DATABASE_QUERY_ERROR': 'Unable to retrieve data',
                'MEDIA_UPLOAD_ERROR': 'Media upload failed',
                'MEDIA_PROCESSING_ERROR': 'Media processing failed',
                'FILE_SIZE_ERROR': 'File size exceeds limit',
                'FILE_TYPE_ERROR': 'File type not supported',
                'UNEXPECTED_ERROR': 'An unexpected error occurred'
            }
            
            return generic_messages.get(error_code, 'An error occurred')
        
        return 'An error occurred'


class AthleteServiceError(Exception):
    """Base exception for athlete service errors with enhanced error handling"""
    
    def __init__(self, message: str, error_code: Union[str, ErrorCode] = None, 
                 details: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None, 
                 operation: Optional[str] = None, timestamp: Optional[str] = None,
                 cause: Optional[Exception] = None):
        # Validate and sanitize message
        sanitized_message = self._sanitize_message(message)
        
        # Handle exception chaining
        if cause:
            super().__init__(sanitized_message)
            self.__cause__ = cause
        else:
            super().__init__(sanitized_message)
        
        # Validate parameters
        self._validate_parameters(message, error_code, user_id, operation)
        
        self.message = sanitized_message
        self.error_code = self._normalize_error_code(error_code)
        self.details = details or {}
        self.user_id = user_id
        self.operation = operation
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.cause = cause
        
        # Add operation to details if provided
        if operation:
            self.details['operation'] = operation
        
        # Add user_id to details if provided (for audit purposes)
        if user_id:
            self.details['user_id'] = user_id
        
        # Log the error with full details (for debugging)
        self._log_error()
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize error message to prevent information disclosure"""
        if not message or not isinstance(message, str):
            return "An error occurred"
        
        # Remove potentially sensitive information
        sensitive_patterns = [
            r'password[:\s]*[^\s]+',  # Remove password values
            r'token[:\s]*[^\s]+',     # Remove token values
            r'secret[:\s]*[^\s]+',    # Remove secret values
            r'key[:\s]*[^\s]+',       # Remove key values
            r'credential[:\s]*[^\s]+', # Remove credential values
            r'api_key[:\s]*[^\s]+',   # Remove API key values
            r'private_key[:\s]*[^\s]+', # Remove private key values
            r'connection_string[:\s]*[^\s]+', # Remove connection strings
            r'file_path[:\s]*[^\s]+', # Remove file paths
            r'stack_trace[:\s]*[^\s]+', # Remove stack traces
        ]
        
        sanitized = message
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()
    
    def _validate_parameters(self, message: str, error_code: Union[str, ErrorCode], 
                           user_id: str, operation: str) -> None:
        """Validate exception parameters"""
        if not message or not isinstance(message, str):
            raise ValueError("Message must be a non-empty string")
        
        if error_code and not isinstance(error_code, (str, ErrorCode)):
            raise ValueError("Error code must be a string or ErrorCode enum")
        
        if user_id and not isinstance(user_id, str):
            raise ValueError("User ID must be a string")
        
        if operation and not isinstance(operation, str):
            raise ValueError("Operation must be a string")
    
    def _normalize_error_code(self, error_code: Union[str, ErrorCode]) -> str:
        """Normalize error code to string format"""
        if isinstance(error_code, ErrorCode):
            return error_code.value
        elif isinstance(error_code, str):
            return error_code
        else:
            return ErrorCode.UNEXPECTED_ERROR.value
    
    def _log_error(self) -> None:
        """Log error with appropriate level based on error code"""
        log_message = f"Error: {self.message}"
        
        if self.error_code:
            log_message += f" (Code: {self.error_code})"
        
        if self.operation:
            log_message += f" (Operation: {self.operation})"
        
        if self.user_id:
            log_message += f" (User: {self.user_id})"
        
        if self.details:
            log_message += f" (Details: {self.details})"
        
        if self.cause:
            log_message += f" (Cause: {str(self.cause)})"
        
        # Log with appropriate level
        if self.error_code in [ErrorCode.AUTHENTICATION_ERROR, ErrorCode.AUTHORIZATION_ERROR]:
            logger.warning(log_message)
        elif self.error_code in [ErrorCode.DATABASE_CONNECTION_ERROR, ErrorCode.UNEXPECTED_ERROR]:
            logger.error(log_message)
        else:
            logger.info(log_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            'error_code': self.error_code,
            'message': self.get_sanitized_message(include_details=True),
            'timestamp': self.timestamp,
            'details': self.details if os.getenv('ENVIRONMENT', 'development').lower() != 'production' else {},
            'request_id': getattr(self, 'request_id', None)
        }
    
    def __str__(self) -> str:
        """String representation of the exception"""
        return self.get_sanitized_message(include_details=True)
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return f"{self.__class__.__name__}(message='{self.message}', error_code='{self.error_code}', details={self.details})"


class ProfileCompletionError(AthleteServiceError, DetailMixin):
    """Raised when there's an error updating profile completion"""
    
    def __init__(self, message: str, profile_id: Optional[str] = None, 
                 completion_percentage: Optional[int] = None, 
                 missing_fields: Optional[List[str]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.PROFILE_COMPLETION_ERROR, **kwargs)
        self.profile_id = profile_id
        self.completion_percentage = completion_percentage
        self.missing_fields = missing_fields or []
        
        # Validate completion percentage
        if completion_percentage is not None and not (0 <= completion_percentage <= 100):
            raise ValueError("completion_percentage must be between 0 and 100")
        
        # Add profile-specific details using mixin
        if profile_id:
            self.add_detail("profile_id", profile_id)
        if completion_percentage is not None:
            self.add_detail("completion_percentage", completion_percentage)
        if missing_fields:
            self.add_detail("missing_fields", missing_fields)
    
    def get_completion_summary(self) -> Dict[str, Any]:
        """Get profile completion summary"""
        return {
            "profile_id": self.profile_id,
            "completion_percentage": self.completion_percentage,
            "missing_fields": self.missing_fields,
            "total_missing": len(self.missing_fields)
        }


class AthleteValidationError(AthleteServiceError, DetailMixin):
    """Raised when athlete data validation fails"""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None, 
                 invalid_data: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.ATHLETE_VALIDATION_ERROR, **kwargs)
        self.field_errors = field_errors or {}
        self.invalid_data = invalid_data or {}
        
        # Add validation-specific details using mixin
        if field_errors:
            self.add_detail("field_errors", field_errors)
        if invalid_data:
            # Sanitize invalid data to prevent sensitive information leakage
            sanitized_data = self._sanitize_sensitive_data(invalid_data)
            self.add_detail("invalid_data", sanitized_data)
    
    def _sanitize_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data fields"""
        sensitive_fields = {'password', 'ssn', 'credit_card', 'email', 'phone'}
        sanitized = {}
        
        for key, value in data.items():
            if key.lower() in sensitive_fields:
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def add_field_error(self, field: str, error: str) -> None:
        """Add a field-specific validation error"""
        self.field_errors[field] = error
        self.add_detail("field_errors", self.field_errors)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get validation error summary"""
        return {
            "total_errors": len(self.field_errors),
            "field_errors": self.field_errors,
            "invalid_fields": list(self.field_errors.keys())
        }
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly validation error message"""
        if self.field_errors:
            fields = ", ".join(self.field_errors.keys())
            return f"Validation failed for the following fields: {fields}. Please check your input and try again."
        return super().get_user_friendly_message()


class AthleteNotFoundError(AthleteServiceError, DetailMixin):
    """Raised when athlete profile is not found"""
    
    def __init__(self, message: str, athlete_id: Optional[str] = None, 
                 search_criteria: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.ATHLETE_NOT_FOUND, **kwargs)
        self.athlete_id = athlete_id
        self.search_criteria = search_criteria or {}
        
        # Add not-found-specific details using mixin
        if athlete_id:
            self.add_detail("athlete_id", athlete_id)
        if search_criteria:
            self.add_detail("search_criteria", search_criteria)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly not-found message"""
        if self.athlete_id:
            return f"Athlete profile with ID {self.athlete_id} was not found."
        return "The requested athlete profile was not found."
    
    def suggest_alternatives(self) -> List[str]:
        """Suggest alternative search strategies"""
        suggestions = [
            "Check if the athlete ID is correct",
            "Verify the athlete profile exists and is active",
            "Try searching with different criteria"
        ]
        return suggestions


class SportCategoryError(AthleteServiceError, DetailMixin):
    """Raised when there's an error with sport category operations"""
    
    def __init__(self, message: str, category_id: Optional[str] = None, 
                 category_name: Optional[str] = None, 
                 available_categories: Optional[List[str]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.SPORT_CATEGORY_ERROR, **kwargs)
        self.category_id = category_id
        self.category_name = category_name
        self.available_categories = available_categories or []
        
        # Add sport category-specific details using mixin
        if category_id:
            self.add_detail("category_id", category_id)
        if category_name:
            self.add_detail("category_name", category_name)
        if available_categories:
            self.add_detail("available_categories", available_categories)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly sport category error message"""
        if self.category_id:
            return f"Sport category with ID {self.category_id} is not valid or not found."
        elif self.category_name:
            return f"Sport category '{self.category_name}' is not valid or not found."
        return "Invalid sport category. Please select a valid sport category."
    
    def get_available_categories(self) -> List[str]:
        """Get list of available sport categories"""
        return self.available_categories


class BulkOperationError(AthleteServiceError, DetailMixin):
    """Raised when bulk operations fail"""
    
    def __init__(self, message: str, operation_type: Optional[str] = None, 
                 total_items: Optional[int] = None, successful_items: Optional[int] = None, 
                 failed_items: Optional[int] = None, 
                 failed_details: Optional[List[Dict[str, Any]]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.BULK_OPERATION_ERROR, **kwargs)
        self.operation_type = operation_type
        self.total_items = total_items or 0
        self.successful_items = successful_items or 0
        self.failed_items = failed_items or 0
        self.failed_details = failed_details or []
        
        # Validate counts
        if self.total_items < 0 or self.successful_items < 0 or self.failed_items < 0:
            raise ValueError("Item counts cannot be negative")
        
        if self.successful_items + self.failed_items > self.total_items:
            raise ValueError("Sum of successful and failed items cannot exceed total items")
        
        # Add bulk operation-specific details using mixin
        if operation_type:
            self.add_detail("operation_type", operation_type)
        
        self.add_details({
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "success_rate": self._calculate_success_rate()
        })
        
        if failed_details:
            self.add_detail("failed_details", failed_details)
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_items == 0:
            return 0.0
        return round((self.successful_items / self.total_items) * 100, 2)
    
    def get_operation_summary(self) -> Dict[str, Any]:
        """Get bulk operation summary"""
        return {
            "operation_type": self.operation_type,
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "success_rate": self._calculate_success_rate(),
            "failed_details": self.failed_details
        }
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly bulk operation error message"""
        return f"Bulk operation failed. {self.successful_items} out of {self.total_items} items were processed successfully."


class RecommendationError(AthleteServiceError, DetailMixin):
    """Raised when athlete recommendation operations fail"""
    
    def __init__(self, message: str, scout_id: Optional[str] = None, 
                 recommendation_type: Optional[str] = None, 
                 preference_data: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.RECOMMENDATION_ERROR, **kwargs)
        self.scout_id = scout_id
        self.recommendation_type = recommendation_type
        self.preference_data = preference_data or {}
        
        # Add recommendation-specific details using mixin
        if scout_id:
            self.add_detail("scout_id", scout_id)
        if recommendation_type:
            self.add_detail("recommendation_type", recommendation_type)
        if preference_data:
            self.add_detail("preference_data", preference_data)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly recommendation error message"""
        return "Unable to generate athlete recommendations at this time. Please try again later."


class StatisticsError(AthleteServiceError, DetailMixin):
    """Raised when statistics operations fail"""
    
    def __init__(self, message: str, statistics_type: Optional[str] = None, 
                 data_range: Optional[Dict[str, Any]] = None, 
                 sample_size: Optional[int] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.STATISTICS_ERROR, **kwargs)
        self.statistics_type = statistics_type
        self.data_range = data_range or {}
        self.sample_size = sample_size
        
        # Validate sample size
        if sample_size is not None and sample_size < 0:
            raise ValueError("sample_size cannot be negative")
        
        # Add statistics-specific details using mixin
        if statistics_type:
            self.add_detail("statistics_type", statistics_type)
        if data_range:
            self.add_detail("data_range", data_range)
        if sample_size:
            self.add_detail("sample_size", sample_size)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly statistics error message"""
        return "Unable to retrieve statistics at this time. Please try again later."


class InputValidationError(AthleteServiceError, DetailMixin):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, invalid_fields: Optional[List[str]] = None, 
                 field_constraints: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.INPUT_VALIDATION_ERROR, **kwargs)
        self.invalid_fields = invalid_fields or []
        self.field_constraints = field_constraints or {}
        
        # Add input validation-specific details using mixin
        if invalid_fields:
            self.add_detail("invalid_fields", invalid_fields)
        if field_constraints:
            self.add_detail("field_constraints", field_constraints)
    
    def add_invalid_field(self, field: str, constraint: Optional[str] = None) -> None:
        """Add an invalid field to the list"""
        self.invalid_fields.append(field)
        if constraint:
            self.field_constraints[field] = constraint
        
        # Update details using mixin
        self.add_detail("invalid_fields", self.invalid_fields)
        self.add_detail("field_constraints", self.field_constraints)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get input validation summary"""
        return {
            "total_invalid_fields": len(self.invalid_fields),
            "invalid_fields": self.invalid_fields,
            "field_constraints": self.field_constraints
        }
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly input validation error message"""
        if self.invalid_fields:
            fields = ", ".join(self.invalid_fields)
            return f"Please check the following fields: {fields}. Make sure they meet the required format and constraints."
        return "Please check your input and make sure it meets the required format and constraints."


class DataSanitizationError(AthleteServiceError, DetailMixin):
    """Raised when data sanitization fails"""
    
    def __init__(self, message: str, original_data: Optional[str] = None, 
                 sanitized_data: Optional[str] = None, 
                 sanitization_rules: Optional[List[str]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.DATA_SANITIZATION_ERROR, **kwargs)
        self.original_data = original_data
        self.sanitized_data = sanitized_data
        self.sanitization_rules = sanitization_rules or []
        
        # Add sanitization-specific details using mixin
        if original_data:
            self.add_detail("original_data", original_data)
        if sanitized_data:
            self.add_detail("sanitized_data", sanitized_data)
        if sanitization_rules:
            self.add_detail("sanitization_rules", sanitization_rules)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly sanitization error message"""
        return "Your input contains invalid characters or formatting. Please check and try again."
    
    def get_sanitization_summary(self) -> Dict[str, Any]:
        """Get data sanitization summary"""
        return {
            "original_data": self.original_data,
            "sanitized_data": self.sanitized_data,
            "sanitization_rules": self.sanitization_rules,
            "data_modified": self.original_data != self.sanitized_data if self.original_data and self.sanitized_data else False
        }


class AuthenticationError(AthleteServiceError, DetailMixin):
    """Raised when authentication fails"""
    
    def __init__(self, message: str, auth_method: Optional[str] = None, 
                 user_identifier: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.AUTHENTICATION_ERROR, **kwargs)
        self.auth_method = auth_method
        self.user_identifier = user_identifier
        
        # Add authentication-specific details using mixin
        if auth_method:
            self.add_detail("auth_method", auth_method)
        if user_identifier:
            self.add_detail("user_identifier", user_identifier)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly authentication error message"""
        return "Authentication failed. Please check your credentials and try again."


class AuthorizationError(AthleteServiceError, DetailMixin):
    """Raised when authorization fails"""
    
    def __init__(self, message: str, required_permission: Optional[str] = None, 
                 user_role: Optional[str] = None, resource: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.AUTHORIZATION_ERROR, **kwargs)
        self.required_permission = required_permission
        self.user_role = user_role
        self.resource = resource
        
        # Add authorization-specific details using mixin
        if required_permission:
            self.add_detail("required_permission", required_permission)
        if user_role:
            self.add_detail("user_role", user_role)
        if resource:
            self.add_detail("resource", resource)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly authorization error message"""
        return "You don't have permission to perform this action."


class RateLimitError(AthleteServiceError, DetailMixin):
    """Raised when rate limits are exceeded"""
    
    def __init__(self, message: str, rate_limit: Optional[int] = None, 
                 reset_time: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.RATE_LIMIT_ERROR, **kwargs)
        self.rate_limit = rate_limit
        self.reset_time = reset_time
        
        # Add rate limit-specific details using mixin
        if rate_limit:
            self.add_detail("rate_limit", rate_limit)
        if reset_time:
            self.add_detail("reset_time", reset_time)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly rate limit error message"""
        return "Too many requests. Please try again later."


class DatabaseConnectionError(AthleteServiceError, DetailMixin):
    """Raised when database connection fails"""
    
    def __init__(self, message: str, database_url: Optional[str] = None, 
                 connection_timeout: Optional[int] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.DATABASE_CONNECTION_ERROR, **kwargs)
        self.database_url = database_url
        self.connection_timeout = connection_timeout
        
        # Add database-specific details using mixin
        if database_url:
            self.add_detail("database_url", database_url)
        if connection_timeout:
            self.add_detail("connection_timeout", connection_timeout)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly database connection error message"""
        return "Database connection failed. Please try again later."


class DatabaseQueryError(AthleteServiceError, DetailMixin):
    """Raised when database queries fail"""
    
    def __init__(self, message: str, query: Optional[str] = None, 
                 query_params: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.DATABASE_QUERY_ERROR, **kwargs)
        self.query = query
        self.query_params = query_params
        
        # Add query-specific details using mixin
        if query:
            self.add_detail("query", query)
        if query_params:
            self.add_detail("query_params", query_params)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly database query error message"""
        return "Database operation failed. Please try again later."


class MediaUploadError(AthleteServiceError, DetailMixin):
    """Raised when media upload fails"""
    
    def __init__(self, message: str, file_name: Optional[str] = None, 
                 file_size: Optional[int] = None, file_type: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.MEDIA_UPLOAD_ERROR, **kwargs)
        self.file_name = file_name
        self.file_size = file_size
        self.file_type = file_type
        
        # Add media-specific details using mixin
        if file_name:
            self.add_detail("file_name", file_name)
        if file_size:
            self.add_detail("file_size", file_size)
        if file_type:
            self.add_detail("file_type", file_type)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly media upload error message"""
        return "File upload failed. Please check your file and try again."


class MediaProcessingError(AthleteServiceError, DetailMixin):
    """Raised when media processing fails"""
    
    def __init__(self, message: str, processing_step: Optional[str] = None, 
                 media_id: Optional[str] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.MEDIA_PROCESSING_ERROR, **kwargs)
        self.processing_step = processing_step
        self.media_id = media_id
        
        # Add processing-specific details using mixin
        if processing_step:
            self.add_detail("processing_step", processing_step)
        if media_id:
            self.add_detail("media_id", media_id)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly media processing error message"""
        return "Media processing failed. Please try again later."


class FileSizeError(AthleteServiceError, DetailMixin):
    """Raised when file size exceeds limits"""
    
    def __init__(self, message: str, file_size: Optional[int] = None, 
                 max_size: Optional[int] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.FILE_SIZE_ERROR, **kwargs)
        self.file_size = file_size
        self.max_size = max_size
        
        # Add file size-specific details using mixin
        if file_size:
            self.add_detail("file_size", file_size)
        if max_size:
            self.add_detail("max_size", max_size)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly file size error message"""
        return "File size exceeds the maximum allowed limit."


class FileTypeError(AthleteServiceError, DetailMixin):
    """Raised when file type is not supported"""
    
    def __init__(self, message: str, file_type: Optional[str] = None, 
                 supported_types: Optional[List[str]] = None, **kwargs):
        super().__init__(message, error_code=ErrorCode.FILE_TYPE_ERROR, **kwargs)
        self.file_type = file_type
        self.supported_types = supported_types or []
        
        # Add file type-specific details using mixin
        if file_type:
            self.add_detail("file_type", file_type)
        if supported_types:
            self.add_detail("supported_types", supported_types)
    
    def get_user_friendly_message(self) -> str:
        """Get user-friendly file type error message"""
        if self.supported_types:
            types = ", ".join(self.supported_types)
            return f"File type not supported. Supported types: {types}"
        return "File type not supported."


# Utility function for creating exceptions with context
def create_athlete_exception(exception_class: type, message: str, **kwargs) -> AthleteServiceError:
    """Create an athlete service exception with proper context"""
    if not issubclass(exception_class, AthleteServiceError):
        raise ValueError(f"exception_class must be a subclass of AthleteServiceError, got {exception_class}")
    
    return exception_class(message, **kwargs)


# Exception handler for converting to API responses
def handle_athlete_exception(exception: Exception) -> Dict[str, Any]:
    """Convert any exception to a standardized API response format"""
    if isinstance(exception, AthleteServiceError):
        return exception.to_dict()
    else:
        # Handle unexpected exceptions
        logger.error(f"Unexpected exception: {str(exception)}", exc_info=True)
        return {
            "error": True,
            "error_code": ErrorCode.UNEXPECTED_ERROR.value,
            "message": "An unexpected error occurred",
            "details": {"original_error": str(exception)},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Exception factory for common scenarios
class ExceptionFactory:
    """Factory for creating common exception types with predefined messages"""
    
    @staticmethod
    def athlete_not_found(athlete_id: str, **kwargs) -> AthleteNotFoundError:
        """Create athlete not found exception"""
        return AthleteNotFoundError(
            f"Athlete with ID {athlete_id} was not found",
            athlete_id=athlete_id,
            **kwargs
        )
    
    @staticmethod
    def validation_error(field: str, message: str, **kwargs) -> AthleteValidationError:
        """Create validation error exception"""
        return AthleteValidationError(
            f"Validation error in field '{field}': {message}",
            field_errors={field: message},
            **kwargs
        )
    
    @staticmethod
    def authentication_failed(auth_method: str, **kwargs) -> AuthenticationError:
        """Create authentication error exception"""
        return AuthenticationError(
            f"Authentication failed using {auth_method}",
            auth_method=auth_method,
            **kwargs
        )
    
    @staticmethod
    def insufficient_permissions(required_permission: str, user_role: str, **kwargs) -> AuthorizationError:
        """Create authorization error exception"""
        return AuthorizationError(
            f"Insufficient permissions. Required: {required_permission}, User role: {user_role}",
            required_permission=required_permission,
            user_role=user_role,
            **kwargs
        )
    
    @staticmethod
    def rate_limit_exceeded(rate_limit: int, **kwargs) -> RateLimitError:
        """Create rate limit error exception"""
        return RateLimitError(
            f"Rate limit exceeded. Maximum {rate_limit} requests allowed",
            rate_limit=rate_limit,
            **kwargs
        ) 