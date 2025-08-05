from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class APIException(HTTPException):
    """Base API exception"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.details = details or {}


class ValidationException(APIException):
    """Validation error exception"""
    def __init__(self, detail: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="VALIDATION_ERROR",
            details=details
        )


class AuthenticationException(APIException):
    """Authentication error exception"""
    def __init__(self, detail: str = "Invalid authentication credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="INVALID_TOKEN"
        )


class AuthorizationException(APIException):
    """Authorization error exception"""
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="ACCESS_DENIED"
        )


class NotFoundException(APIException):
    """Resource not found exception"""
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id {resource_id} not found",
            error_code="RESOURCE_NOT_FOUND"
        )


class ConflictException(APIException):
    """Resource conflict exception"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="RESOURCE_CONFLICT"
        )


class RateLimitException(APIException):
    """Rate limit exceeded exception"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after}
        )


class InternalServerException(APIException):
    """Internal server error exception"""
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="INTERNAL_SERVER_ERROR"
        )


class ServiceUnavailableException(APIException):
    """Service unavailable exception"""
    def __init__(self, detail: str = "Service temporarily unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="SERVICE_UNAVAILABLE"
        )


# Service-specific exceptions
class UserNotFoundError(APIException):
    """User not found exception"""
    def __init__(self, user_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
            error_code="USER_NOT_FOUND"
        )


class UserAlreadyExistsError(APIException):
    """User already exists exception"""
    def __init__(self, email: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {email} already exists",
            error_code="USER_ALREADY_EXISTS"
        )


class InvalidUserDataError(APIException):
    """Invalid user data exception"""
    def __init__(self, detail: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="INVALID_USER_DATA",
            details=details
        )


class UserProfileNotFoundError(APIException):
    """User profile not found exception"""
    def __init__(self, user_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User profile for {user_id} not found",
            error_code="USER_PROFILE_NOT_FOUND"
        )


# Additional exceptions for compatibility with existing API files
class ValidationError(APIException):
    """Validation error exception (alias for ValidationException)"""
    def __init__(self, detail: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="VALIDATION_ERROR",
            details=details
        )


class ResourceNotFoundError(APIException):
    """Resource not found exception (alias for NotFoundException)"""
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} with id {resource_id} not found",
            error_code="RESOURCE_NOT_FOUND"
        )


class AuthorizationError(APIException):
    """Authorization error exception (alias for AuthorizationException)"""
    def __init__(self, detail: str = "Access denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="ACCESS_DENIED"
        )


class DatabaseError(APIException):
    """Database error exception"""
    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="DATABASE_ERROR"
        ) 