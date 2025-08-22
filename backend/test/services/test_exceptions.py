"""
Test suite for the improved exception service
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.exceptions import (
    AthleteServiceError, ProfileCompletionError, AthleteValidationError,
    AthleteNotFoundError, SportCategoryError, BulkOperationError,
    RecommendationError, StatisticsError, InputValidationError,
    DataSanitizationError, AuthenticationError, AuthorizationError,
    RateLimitError, DatabaseConnectionError, DatabaseQueryError,
    MediaUploadError, MediaProcessingError, FileSizeError, FileTypeError,
    ErrorCode, DetailMixin, create_athlete_exception, handle_athlete_exception,
    ExceptionFactory
)


class TestErrorCode:
    """Test ErrorCode enum functionality"""
    
    def test_error_code_values(self):
        """Test that error codes have expected values"""
        assert ErrorCode.ATHLETE_SERVICE_ERROR.value == "ATHLETE_SERVICE_ERROR"
        assert ErrorCode.AUTHENTICATION_ERROR.value == "AUTHENTICATION_ERROR"
        assert ErrorCode.MEDIA_UPLOAD_ERROR.value == "MEDIA_UPLOAD_ERROR"
    
    def test_error_code_enumeration(self):
        """Test that all error codes are properly defined"""
        expected_codes = [
            "ATHLETE_SERVICE_ERROR", "UNEXPECTED_ERROR", "PROFILE_COMPLETION_ERROR",
            "ATHLETE_VALIDATION_ERROR", "ATHLETE_NOT_FOUND", "INPUT_VALIDATION_ERROR",
            "SPORT_CATEGORY_ERROR", "BULK_OPERATION_ERROR", "RECOMMENDATION_ERROR",
            "STATISTICS_ERROR", "DATA_SANITIZATION_ERROR", "AUTHENTICATION_ERROR",
            "AUTHORIZATION_ERROR", "RATE_LIMIT_ERROR", "DATABASE_CONNECTION_ERROR",
            "DATABASE_QUERY_ERROR", "MEDIA_UPLOAD_ERROR", "MEDIA_PROCESSING_ERROR",
            "FILE_SIZE_ERROR", "FILE_TYPE_ERROR"
        ]
        
        for code in expected_codes:
            assert hasattr(ErrorCode, code.replace("_", "").title())


class TestDetailMixin:
    """Test DetailMixin functionality"""
    
    def test_add_detail(self):
        """Test adding a single detail"""
        mixin = DetailMixin()
        mixin.details = {}
        
        mixin.add_detail("test_key", "test_value")
        assert mixin.details["test_key"] == "test_value"
    
    def test_add_details(self):
        """Test adding multiple details at once"""
        mixin = DetailMixin()
        mixin.details = {}
        
        details_dict = {"key1": "value1", "key2": "value2"}
        mixin.add_details(details_dict)
        
        assert mixin.details["key1"] == "value1"
        assert mixin.details["key2"] == "value2"
    
    def test_get_detail(self):
        """Test getting a detail value"""
        mixin = DetailMixin()
        mixin.details = {"test_key": "test_value"}
        
        assert mixin.get_detail("test_key") == "test_value"
        assert mixin.get_detail("nonexistent", "default") == "default"


class TestAthleteServiceError:
    """Test base AthleteServiceError functionality"""
    
    def test_basic_initialization(self):
        """Test basic exception initialization"""
        error = AthleteServiceError("Test error message")
        
        assert error.message == "Test error message"
        assert error.error_code == "ATHLETE_SERVICE_ERROR"
        assert error.details == {}
        assert error.user_id is None
        assert error.operation is None
        assert error.timestamp is not None
        assert error.cause is None
    
    def test_full_initialization(self):
        """Test full exception initialization with all parameters"""
        timestamp = "2023-01-01T00:00:00Z"
        error = AthleteServiceError(
            message="Test error",
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            details={"key": "value"},
            user_id="user123",
            operation="test_operation",
            timestamp=timestamp
        )
        
        assert error.message == "Test error"
        assert error.error_code == "AUTHENTICATION_ERROR"
        assert error.details == {"key": "value"}
        assert error.user_id == "user123"
        assert error.operation == "test_operation"
        assert error.timestamp == timestamp
    
    def test_exception_chaining(self):
        """Test exception chaining functionality"""
        original_error = ValueError("Original error")
        error = AthleteServiceError("Test error", cause=original_error)
        
        assert error.cause == original_error
        assert error.__cause__ == original_error
    
    def test_message_sanitization(self):
        """Test message sanitization for sensitive data"""
        sensitive_message = "User email@example.com with card 1234-5678-9012-3456 failed"
        error = AthleteServiceError(sensitive_message)
        
        assert "[EMAIL]" in error.message
        assert "[CARD_NUMBER]" in error.message
        assert "email@example.com" not in error.message
        assert "1234-5678-9012-3456" not in error.message
    
    def test_message_length_limit(self):
        """Test message length limiting"""
        long_message = "x" * 600
        error = AthleteServiceError(long_message)
        
        assert len(error.message) <= 500
        assert error.message.endswith("...")
    
    def test_parameter_validation(self):
        """Test parameter validation"""
        with pytest.raises(ValueError, match="Error message cannot be empty"):
            AthleteServiceError("")
        
        with pytest.raises(ValueError, match="user_id must be a string"):
            AthleteServiceError("Test", user_id=123)
        
        with pytest.raises(ValueError, match="operation must be a string"):
            AthleteServiceError("Test", operation=456)
    
    def test_to_dict(self):
        """Test conversion to dictionary format"""
        error = AthleteServiceError(
            "Test error",
            user_id="user123",
            operation="test_op"
        )
        
        result = error.to_dict()
        
        assert result["error"] is True
        assert result["error_code"] == "ATHLETE_SERVICE_ERROR"
        assert result["message"] == "Test error"
        assert result["user_id"] == "user123"
        assert result["operation"] == "test_op"
        assert "timestamp" in result
    
    def test_to_dict_with_cause(self):
        """Test to_dict includes cause when available"""
        original_error = ValueError("Original")
        error = AthleteServiceError("Test", cause=original_error)
        
        result = error.to_dict()
        assert "cause" in result
        assert result["cause"] == "Original"
    
    def test_get_user_friendly_message(self):
        """Test user-friendly message generation"""
        error = AthleteServiceError("Technical error message")
        user_message = error.get_user_friendly_message()
        
        assert "Technical error message" in user_message
        assert user_message.startswith("An error occurred:")
    
    def test_string_representation(self):
        """Test string representation with and without cause"""
        error1 = AthleteServiceError("Test error")
        assert str(error1) == "Test error"
        
        original_error = ValueError("Original")
        error2 = AthleteServiceError("Test error", cause=original_error)
        assert "caused by: Original" in str(error2)


class TestProfileCompletionError:
    """Test ProfileCompletionError functionality"""
    
    def test_initialization(self):
        """Test profile completion error initialization"""
        error = ProfileCompletionError(
            "Profile incomplete",
            profile_id="profile123",
            completion_percentage=75,
            missing_fields=["bio", "photo"]
        )
        
        assert error.profile_id == "profile123"
        assert error.completion_percentage == 75
        assert error.missing_fields == ["bio", "photo"]
        assert error.details["profile_id"] == "profile123"
        assert error.details["completion_percentage"] == 75
        assert error.details["missing_fields"] == ["bio", "photo"]
    
    def test_completion_percentage_validation(self):
        """Test completion percentage validation"""
        with pytest.raises(ValueError, match="completion_percentage must be between 0 and 100"):
            ProfileCompletionError("Test", completion_percentage=150)
        
        with pytest.raises(ValueError, match="completion_percentage must be between 0 and 100"):
            ProfileCompletionError("Test", completion_percentage=-10)
    
    def test_get_completion_summary(self):
        """Test completion summary generation"""
        error = ProfileCompletionError(
            "Profile incomplete",
            profile_id="profile123",
            completion_percentage=60,
            missing_fields=["bio", "photo", "stats"]
        )
        
        summary = error.get_completion_summary()
        
        assert summary["profile_id"] == "profile123"
        assert summary["completion_percentage"] == 60
        assert summary["missing_fields"] == ["bio", "photo", "stats"]
        assert summary["total_missing"] == 3


class TestAthleteValidationError:
    """Test AthleteValidationError functionality"""
    
    def test_initialization(self):
        """Test athlete validation error initialization"""
        field_errors = {"name": "Required field", "age": "Must be positive"}
        invalid_data = {"name": "", "age": -5}
        
        error = AthleteValidationError(
            "Validation failed",
            field_errors=field_errors,
            invalid_data=invalid_data
        )
        
        assert error.field_errors == field_errors
        assert error.invalid_data == invalid_data
        assert error.details["field_errors"] == field_errors
        assert error.details["invalid_data"] == invalid_data
    
    def test_add_field_error(self):
        """Test adding field errors dynamically"""
        error = AthleteValidationError("Validation failed")
        error.add_field_error("email", "Invalid email format")
        
        assert error.field_errors["email"] == "Invalid email format"
        assert error.details["field_errors"]["email"] == "Invalid email format"
    
    def test_get_validation_summary(self):
        """Test validation summary generation"""
        error = AthleteValidationError(
            "Validation failed",
            field_errors={"name": "Required", "age": "Invalid"}
        )
        
        summary = error.get_validation_summary()
        
        assert summary["total_errors"] == 2
        assert summary["field_errors"] == {"name": "Required", "age": "Invalid"}
        assert summary["invalid_fields"] == ["name", "age"]
    
    def test_get_user_friendly_message(self):
        """Test user-friendly validation message"""
        error = AthleteValidationError(
            "Validation failed",
            field_errors={"name": "Required", "age": "Invalid"}
        )
        
        message = error.get_user_friendly_message()
        assert "name" in message
        assert "age" in message
        assert "Please check your input" in message
    
    def test_sensitive_data_sanitization(self):
        """Test that sensitive data is sanitized in details"""
        invalid_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "password": "secret123",
            "ssn": "123-45-6789"
        }
        
        error = AthleteValidationError("Validation failed", invalid_data=invalid_data)
        
        # Sensitive fields should be redacted
        assert error.details["invalid_data"]["password"] == "[REDACTED]"
        assert error.details["invalid_data"]["ssn"] == "[REDACTED]"
        
        # Non-sensitive fields should remain
        assert error.details["invalid_data"]["name"] == "John Doe"
        assert error.details["invalid_data"]["email"] == "[REDACTED]"


class TestBulkOperationError:
    """Test BulkOperationError functionality"""
    
    def test_initialization(self):
        """Test bulk operation error initialization"""
        error = BulkOperationError(
            "Bulk operation failed",
            operation_type="import",
            total_items=100,
            successful_items=80,
            failed_items=20,
            failed_details=[{"id": "1", "reason": "Invalid data"}]
        )
        
        assert error.operation_type == "import"
        assert error.total_items == 100
        assert error.successful_items == 80
        assert error.failed_items == 20
        assert error.failed_details == [{"id": "1", "reason": "Invalid data"}]
        assert error.details["success_rate"] == 80.0
    
    def test_count_validation(self):
        """Test count validation"""
        with pytest.raises(ValueError, match="Item counts cannot be negative"):
            BulkOperationError("Test", total_items=-10)
        
        with pytest.raises(ValueError, match="Item counts cannot be negative"):
            BulkOperationError("Test", successful_items=-5)
        
        with pytest.raises(ValueError, match="Sum of successful and failed items cannot exceed total items"):
            BulkOperationError("Test", total_items=10, successful_items=8, failed_items=5)
    
    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        error = BulkOperationError("Test", total_items=100, successful_items=75, failed_items=25)
        assert error.details["success_rate"] == 75.0
        
        error = BulkOperationError("Test", total_items=0)
        assert error.details["success_rate"] == 0.0
    
    def test_get_operation_summary(self):
        """Test operation summary generation"""
        error = BulkOperationError(
            "Test",
            operation_type="export",
            total_items=50,
            successful_items=45,
            failed_items=5
        )
        
        summary = error.get_operation_summary()
        
        assert summary["operation_type"] == "export"
        assert summary["total_items"] == 50
        assert summary["successful_items"] == 45
        assert summary["failed_items"] == 5
        assert summary["success_rate"] == 90.0


class TestNewExceptionTypes:
    """Test the new exception types added"""
    
    def test_authentication_error(self):
        """Test AuthenticationError"""
        error = AuthenticationError(
            "Login failed",
            auth_method="password",
            user_identifier="user@example.com"
        )
        
        assert error.auth_method == "password"
        assert error.user_identifier == "user@example.com"
        assert error.details["auth_method"] == "password"
        assert error.details["user_identifier"] == "user@example.com"
    
    def test_authorization_error(self):
        """Test AuthorizationError"""
        error = AuthorizationError(
            "Access denied",
            required_permission="admin",
            user_role="user",
            resource="user_management"
        )
        
        assert error.required_permission == "admin"
        assert error.user_role == "user"
        assert error.resource == "user_management"
    
    def test_rate_limit_error(self):
        """Test RateLimitError"""
        error = RateLimitError(
            "Too many requests",
            rate_limit=100,
            reset_time="2023-01-01T01:00:00Z"
        )
        
        assert error.rate_limit == 100
        assert error.reset_time == "2023-01-01T01:00:00Z"
    
    def test_database_connection_error(self):
        """Test DatabaseConnectionError"""
        error = DatabaseConnectionError(
            "Connection failed",
            database_url="postgresql://localhost:5432/db",
            connection_timeout=30
        )
        
        assert error.database_url == "postgresql://localhost:5432/db"
        assert error.connection_timeout == 30
    
    def test_media_upload_error(self):
        """Test MediaUploadError"""
        error = MediaUploadError(
            "Upload failed",
            file_name="video.mp4",
            file_size=1048576,
            file_type="video/mp4"
        )
        
        assert error.file_name == "video.mp4"
        assert error.file_size == 1048576
        assert error.file_type == "video/mp4"


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_athlete_exception(self):
        """Test create_athlete_exception function"""
        error = create_athlete_exception(
            AthleteNotFoundError,
            "Not found",
            athlete_id="123"
        )
        
        assert isinstance(error, AthleteNotFoundError)
        assert error.athlete_id == "123"
    
    def test_create_athlete_exception_invalid_class(self):
        """Test create_athlete_exception with invalid class"""
        with pytest.raises(ValueError, match="must be a subclass of AthleteServiceError"):
            create_athlete_exception(Exception, "Test")
    
    def test_handle_athlete_exception_custom(self):
        """Test handle_athlete_exception with custom exception"""
        error = AthleteNotFoundError("Not found")
        result = handle_athlete_exception(error)
        
        assert result["error"] is True
        assert result["error_code"] == "ATHLETE_NOT_FOUND"
        assert result["message"] == "Not found"
    
    def test_handle_athlete_exception_unexpected(self):
        """Test handle_athlete_exception with unexpected exception"""
        unexpected_error = ValueError("Unexpected")
        result = handle_athlete_exception(unexpected_error)
        
        assert result["error"] is True
        assert result["error_code"] == "UNEXPECTED_ERROR"
        assert "original_error" in result["details"]


class TestExceptionFactory:
    """Test ExceptionFactory functionality"""
    
    def test_athlete_not_found(self):
        """Test athlete not found factory method"""
        error = ExceptionFactory.athlete_not_found("athlete123")
        
        assert isinstance(error, AthleteNotFoundError)
        assert error.athlete_id == "athlete123"
        assert "athlete123" in error.message
    
    def test_validation_error(self):
        """Test validation error factory method"""
        error = ExceptionFactory.validation_error("email", "Invalid format")
        
        assert isinstance(error, AthleteValidationError)
        assert error.field_errors["email"] == "Invalid format"
        assert "email" in error.message
    
    def test_authentication_failed(self):
        """Test authentication failed factory method"""
        error = ExceptionFactory.authentication_failed("oauth")
        
        assert isinstance(error, AuthenticationError)
        assert error.auth_method == "oauth"
        assert "oauth" in error.message
    
    def test_insufficient_permissions(self):
        """Test insufficient permissions factory method"""
        error = ExceptionFactory.insufficient_permissions("delete", "user")
        
        assert isinstance(error, AuthorizationError)
        assert error.required_permission == "delete"
        assert error.user_role == "user"
    
    def test_rate_limit_exceeded(self):
        """Test rate limit exceeded factory method"""
        error = ExceptionFactory.rate_limit_exceeded(1000)
        
        assert isinstance(error, RateLimitError)
        assert error.rate_limit == 1000
        assert "1000" in error.message


class TestIntegration:
    """Integration tests for exception handling"""
    
    def test_exception_chain_with_logging(self):
        """Test that exceptions are properly logged"""
        with patch('app.services.exceptions.logger') as mock_logger:
            error = AthleteServiceError("Test error", user_id="user123")
            
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "user123" in log_call
    
    def test_exception_to_api_response(self):
        """Test complete exception to API response flow"""
        error = AthleteValidationError(
            "Validation failed",
            field_errors={"name": "Required"},
            user_id="user123",
            operation="profile_update"
        )
        
        api_response = error.to_dict()
        
        assert api_response["error"] is True
        assert api_response["error_code"] == "ATHLETE_VALIDATION_ERROR"
        assert api_response["user_id"] == "user123"
        assert api_response["operation"] == "profile_update"
        assert "field_errors" in api_response["details"]
    
    def test_mixin_integration(self):
        """Test that DetailMixin works properly with exceptions"""
        error = ProfileCompletionError("Profile incomplete")
        error.add_detail("custom_key", "custom_value")
        
        assert error.get_detail("custom_key") == "custom_value"
        assert error.details["custom_key"] == "custom_value" 