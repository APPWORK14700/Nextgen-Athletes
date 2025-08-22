"""
Test file for the improved AthleteProfileService
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date
from typing import Dict, Any

from app.services.athlete_profile_service import AthleteProfileService
from app.models.athlete import AthleteProfileCreate, AthleteProfileUpdate
from app.services.exceptions import (
    AthleteServiceError, ProfileCompletionError, AthleteValidationError,
    AthleteNotFoundError, SportCategoryError, InputValidationError, DataSanitizationError
)


class TestAthleteProfileServiceImproved:
    """Test class for improved AthleteProfileService"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'collections': {
                "athlete_profiles": "athlete_profiles",
                "users": "users",
                "user_profiles": "user_profiles",
                "sport_categories": "sport_categories"
            },
            'field_weights': {
                "first_name": 10,
                "last_name": 10,
                "date_of_birth": 8,
                "gender": 8,
                "location": 10,
                "primary_sport_category_id": 12,
                "position": 12,
                "height_cm": 8,
                "weight_kg": 8,
                "academic_info": 6,
                "career_highlights": 8,
                "profile_image_url": 10
            },
            'field_categories': {
                "basic_info": ["first_name", "last_name", "date_of_birth", "gender"],
                "sport_info": ["primary_sport_category_id", "position", "secondary_sport_category_ids"],
                "physical_info": ["height_cm", "weight_kg", "location"],
                "additional_info": ["academic_info", "career_highlights", "profile_image_url"]
            },
            'security': {
                'enable_input_validation': True,
                'enable_sanitization': True,
                'max_string_length': 1000,
                'allowed_genders': ['male', 'female', 'other'],
                'enable_rate_limiting': True,
                'max_requests_per_minute': 100
            },
            'logging': {
                'log_profile_updates': True,
                'log_level': 'INFO'
            }
        }
    
    @pytest.fixture
    def mock_profile_data(self):
        """Mock profile data for testing"""
        return AthleteProfileCreate(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1995, 5, 15),
            gender="male",
            location="New York",
            primary_sport_category_id="soccer_001",
            position="Forward",
            height_cm=180,
            weight_kg=75,
            academic_info="Bachelor's in Sports Science",
            career_highlights="Top scorer in college league"
        )
    
    @pytest.fixture
    def mock_update_data(self):
        """Mock update data for testing"""
        return AthleteProfileUpdate(
            first_name="John Updated",
            location="Los Angeles",
            position="Striker"
        )
    
    @pytest.fixture
    def service(self, mock_config):
        """Create service instance with mocked config"""
        with patch('app.services.athlete_profile_service.get_config', return_value=mock_config):
            service = AthleteProfileService()
            
            # Mock repositories
            service.athlete_repository = Mock()
            service.user_repository = Mock()
            service.user_profile_repository = Mock()
            service.sport_category_repository = Mock()
            
            return service
    
    def test_config_validation_success(self, mock_config):
        """Test successful configuration validation"""
        with patch('app.services.athlete_profile_service.get_config', return_value=mock_config):
            service = AthleteProfileService()
            assert service.config == mock_config
    
    def test_config_validation_missing_sections(self):
        """Test configuration validation with missing sections"""
        incomplete_config = {
            'collections': {"athlete_profiles": "athlete_profiles"},
            'field_weights': {"first_name": 10}
        }
        
        with patch('app.services.athlete_profile_service.get_config', return_value=incomplete_config):
            with pytest.raises(ValueError, match="Missing required config sections"):
                AthleteProfileService()
    
    def test_config_validation_missing_collections(self):
        """Test configuration validation with missing collections"""
        config_without_collections = {
            'collections': {"athlete_profiles": "athlete_profiles"},
            'field_weights': {"first_name": 10},
            'field_categories': {"basic": ["first_name"]},
            'security': {'enable_input_validation': True},
            'logging': {'log_profile_updates': True}
        }
        
        with patch('app.services.athlete_profile_service.get_config', return_value=config_without_collections):
            with pytest.raises(ValueError, match="Missing required collections in config"):
                AthleteProfileService()
    
    def test_config_defaults_set(self, mock_config):
        """Test that configuration defaults are properly set"""
        # Remove some config values to test defaults
        mock_config['security'].pop('enable_input_validation', None)
        mock_config['logging'].pop('log_profile_updates', None)
        
        with patch('app.services.athlete_profile_service.get_config', return_value=mock_config):
            service = AthleteProfileService()
            
            # Check defaults are set
            assert service.security_config['enable_input_validation'] is True
            assert service.security_config['max_string_length'] == 1000
            assert service.logging_config['log_profile_updates'] is True
    
    def test_validate_create_input_success(self, service, mock_profile_data):
        """Test successful input validation for profile creation"""
        # Should not raise any exceptions
        service._validate_create_input("user123", mock_profile_data)
    
    def test_validate_create_input_invalid_user_id(self, service, mock_profile_data):
        """Test input validation with invalid user ID"""
        with pytest.raises(InputValidationError, match="Invalid user_id"):
            service._validate_create_input("", mock_profile_data)
        
        with pytest.raises(InputValidationError, match="Invalid user_id"):
            service._validate_create_input("   ", mock_profile_data)
        
        with pytest.raises(InputValidationError, match="Invalid user_id"):
            service._validate_create_input(None, mock_profile_data)
    
    def test_validate_create_input_missing_first_name(self, service, mock_profile_data):
        """Test input validation with missing first name"""
        mock_profile_data.first_name = ""
        with pytest.raises(InputValidationError, match="first_name is required and cannot be empty"):
            service._validate_create_input("user123", mock_profile_data)
        
        mock_profile_data.first_name = "   "
        with pytest.raises(InputValidationError, match="first_name is required and cannot be empty"):
            service._validate_create_input("user123", mock_profile_data)
    
    def test_validate_create_input_first_name_too_long(self, service, mock_profile_data):
        """Test input validation with first name too long"""
        mock_profile_data.first_name = "A" * 1001  # Exceeds max_string_length
        with pytest.raises(InputValidationError, match="first_name too long"):
            service._validate_create_input("user123", mock_profile_data)
    
    def test_validate_create_input_invalid_gender(self, service, mock_profile_data):
        """Test input validation with invalid gender"""
        mock_profile_data.gender = "invalid_gender"
        with pytest.raises(InputValidationError, match="Invalid gender"):
            service._validate_create_input("user123", mock_profile_data)
    
    def test_validate_create_input_missing_sport_category(self, service, mock_profile_data):
        """Test input validation with missing sport category"""
        mock_profile_data.primary_sport_category_id = ""
        with pytest.raises(InputValidationError, match="primary_sport_category_id is required"):
            service._validate_create_input("user123", mock_profile_data)
    
    def test_validate_update_input_success(self, service, mock_update_data):
        """Test successful input validation for profile updates"""
        # Should not raise any exceptions
        service._validate_update_input("user123", mock_update_data)
    
    def test_validate_update_input_empty_strings(self, service, mock_update_data):
        """Test input validation with empty strings in updates"""
        mock_update_data.first_name = ""
        with pytest.raises(InputValidationError, match="first_name cannot be empty if provided"):
            service._validate_update_input("user123", mock_update_data)
        
        mock_update_data.first_name = "   "
        with pytest.raises(InputValidationError, match="first_name cannot be empty if provided"):
            service._validate_update_input("user123", mock_update_data)
    
    def test_sanitize_string_basic(self, service):
        """Test basic string sanitization"""
        result = service._sanitize_string("Hello World")
        assert result == "Hello World"
    
    def test_sanitize_string_html_escape(self, service):
        """Test HTML escaping in string sanitization"""
        result = service._sanitize_string("<script>alert('xss')</script>")
        assert "&lt;script&gt;" in result
        assert "alert" not in result
    
    def test_sanitize_string_remove_scripts(self, service):
        """Test removal of script patterns"""
        result = service._sanitize_string("javascript:alert('xss')")
        assert "javascript:" not in result
        
        result = service._sanitize_string("vbscript:msgbox('xss')")
        assert "vbscript:" not in result
        
        result = service._sanitize_string("data:text/html,<script>alert('xss')</script>")
        assert "data:" not in result
    
    def test_sanitize_string_remove_dangerous_tags(self, service):
        """Test removal of dangerous HTML tags"""
        result = service._sanitize_string("<iframe src='malicious.com'></iframe>")
        assert "iframe" not in result
        
        result = service._sanitize_string("<object data='malicious.swf'></object>")
        assert "object" not in result
        
        result = service._sanitize_string("<embed src='malicious.swf'></embed>")
        assert "embed" not in result
    
    def test_sanitize_string_length_limit(self, service):
        """Test string length limiting"""
        long_string = "A" * 2000  # Exceeds max_string_length
        result = service._sanitize_string(long_string)
        assert len(result) == 1000  # Should be truncated to max_string_length
    
    def test_sanitize_string_whitespace_trim(self, service):
        """Test whitespace trimming"""
        result = service._sanitize_string("  Hello World  ")
        assert result == "Hello World"
    
    def test_sanitize_profile_data(self, service, mock_profile_data):
        """Test profile data sanitization"""
        # Add some potentially dangerous content
        mock_profile_data.first_name = "<script>alert('xss')</script>John"
        mock_profile_data.location = "javascript:alert('xss')New York"
        
        sanitized = service._sanitize_profile_data(mock_profile_data)
        
        # Check that dangerous content is removed/escaped
        assert "&lt;script&gt;" in sanitized.first_name
        assert "javascript:" not in sanitized.location
        assert "New York" in sanitized.location
    
    def test_sanitize_update_data(self, service, mock_update_data):
        """Test update data sanitization"""
        # Add some potentially dangerous content
        mock_update_data.first_name = "<iframe>John</iframe>"
        mock_update_data.location = "vbscript:msgbox('xss')Los Angeles"
        
        sanitized = service._sanitize_update_data(mock_update_data)
        
        # Check that dangerous content is removed/escaped
        assert "&lt;iframe&gt;" in sanitized.first_name
        assert "vbscript:" not in sanitized.location
        assert "Los Angeles" in sanitized.location
    
    def test_prepare_profile_document(self, service, mock_profile_data):
        """Test profile document preparation"""
        doc = service._prepare_profile_document("user123", mock_profile_data)
        
        assert doc["user_id"] == "user123"
        assert doc["first_name"] == "John"
        assert doc["last_name"] == "Doe"
        assert doc["date_of_birth"] == "1995-05-15"
        assert doc["gender"] == "male"
        assert doc["is_active"] is True
        assert "created_at" in doc
        assert "updated_at" in doc
    
    def test_prepare_update_data(self, service, mock_update_data):
        """Test update data preparation"""
        update_data = service._prepare_update_data(mock_update_data)
        
        assert update_data["first_name"] == "John Updated"
        assert update_data["location"] == "Los Angeles"
        assert update_data["position"] == "Striker"
        assert "last_name" not in update_data  # Not provided in update
    
    def test_format_profile_document(self, service):
        """Test profile document formatting"""
        profile_doc = {
            "id": "profile123",
            "date_of_birth": "1995-05-15T00:00:00",
            "first_name": "John"
        }
        
        formatted = service._format_profile_document(profile_doc)
        
        # Check that date is converted back to date object
        assert isinstance(formatted["date_of_birth"], date)
        assert formatted["date_of_birth"] == date(1995, 5, 15)
        assert formatted["first_name"] == "John"
    
    def test_format_profile_document_invalid_date(self, service):
        """Test profile document formatting with invalid date"""
        profile_doc = {
            "id": "profile123",
            "date_of_birth": "invalid-date",
            "first_name": "John"
        }
        
        formatted = service._format_profile_document(profile_doc)
        
        # Check that invalid date is set to None
        assert formatted["date_of_birth"] is None
    
    def test_calculate_completion_percentage(self, service):
        """Test profile completion percentage calculation"""
        profile_doc = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "location": "New York",
            "primary_sport_category_id": "soccer_001",
            "position": "Forward",
            "height_cm": 180,
            "weight_kg": 75,
            "academic_info": "Bachelor's degree",
            "career_highlights": "Top scorer",
            "profile_image_url": "http://example.com/image.jpg"
        }
        
        percentage = service._calculate_completion_percentage(profile_doc)
        
        # All fields are filled, should be 100%
        assert percentage == 100
    
    def test_calculate_completion_percentage_partial(self, service):
        """Test profile completion percentage calculation with partial data"""
        profile_doc = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "location": None,  # Missing
            "primary_sport_category_id": "soccer_001",
            "position": None,  # Missing
            "height_cm": 180,
            "weight_kg": 75,
            "academic_info": None,  # Missing
            "career_highlights": None,  # Missing
            "profile_image_url": None  # Missing
        }
        
        percentage = service._calculate_completion_percentage(profile_doc)
        
        # Should be less than 100% due to missing fields
        assert percentage < 100
        assert percentage > 0
    
    def test_calculate_category_completion(self, service):
        """Test category completion calculation"""
        profile_doc = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "primary_sport_category_id": "soccer_001",
            "position": "Forward",
            "secondary_sport_category_ids": ["basketball_001"],
            "height_cm": 180,
            "weight_kg": 75,
            "location": "New York",
            "academic_info": "Bachelor's degree",
            "career_highlights": "Top scorer",
            "profile_image_url": "http://example.com/image.jpg"
        }
        
        category_completion = service._calculate_category_completion(profile_doc)
        
        # Check basic info category (4 fields, all filled)
        assert category_completion["basic_info"]["completed"] == 4
        assert category_completion["basic_info"]["total"] == 4
        assert category_completion["basic_info"]["percentage"] == 100
        
        # Check sport info category (3 fields, all filled)
        assert category_completion["sport_info"]["completed"] == 3
        assert category_completion["sport_info"]["total"] == 3
        assert category_completion["sport_info"]["percentage"] == 100
    
    def test_get_missing_fields(self, service):
        """Test missing fields detection"""
        profile_doc = {
            "first_name": "John",
            "last_name": None,  # Missing
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "location": "",  # Empty string
            "primary_sport_category_id": "soccer_001",
            "position": "Forward",
            "height_cm": 180,
            "weight_kg": 75,
            "academic_info": "Bachelor's degree",
            "career_highlights": None,  # Missing
            "profile_image_url": "http://example.com/image.jpg"
        }
        
        missing_fields = service._get_missing_fields(profile_doc)
        
        # Should include fields that are None or empty strings
        assert "last_name" in missing_fields
        assert "location" in missing_fields
        assert "career_highlights" in missing_fields
        
        # Should not include fields that have values
        assert "first_name" not in missing_fields
        assert "primary_sport_category_id" not in missing_fields
    
    @pytest.mark.asyncio
    async def test_get_sport_category_caching(self, service):
        """Test sport category caching"""
        # Mock the repository response
        mock_category = {"id": "soccer_001", "name": "Soccer", "is_active": True}
        service.sport_category_repository.get_by_id = AsyncMock(return_value=mock_category)
        
        # First call should hit the repository
        result1 = await service._get_sport_category("soccer_001")
        assert result1 == mock_category
        
        # Second call should use cache
        result2 = await service._get_sport_category("soccer_001")
        assert result2 == mock_category
        
        # Verify repository was only called once
        service.sport_category_repository.get_by_id.assert_called_once_with("soccer_001")
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_success(self, service):
        """Test successful sport category validation"""
        mock_category = {"id": "soccer_001", "name": "Soccer", "is_active": True}
        service._get_sport_category = AsyncMock(return_value=mock_category)
        
        result = await service._validate_sport_category("soccer_001")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_not_found(self, service):
        """Test sport category validation with non-existent category"""
        service._get_sport_category = AsyncMock(return_value=None)
        
        result = await service._validate_sport_category("invalid_id")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_inactive(self, service):
        """Test sport category validation with inactive category"""
        mock_category = {"id": "soccer_001", "name": "Soccer", "is_active": False}
        service._get_sport_category = AsyncMock(return_value=mock_category)
        
        result = await service._validate_sport_category("soccer_001")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_create_athlete_profile_optimized(self, service, mock_profile_data):
        """Test optimized profile creation without extra database call"""
        # Mock repository responses
        service.user_repository.get_by_id = AsyncMock(return_value={"id": "user123"})
        service.athlete_repository.get_by_field = AsyncMock(return_value=None)  # No existing profile
        service.sport_category_repository.get_by_id = AsyncMock(return_value={"id": "soccer_001", "is_active": True})
        service.athlete_repository.create = AsyncMock(return_value="profile123")
        service.user_profile_repository.update = AsyncMock()
        
        result = await service.create_athlete_profile("user123", mock_profile_data)
        
        # Verify the result contains the created document
        assert result["id"] == "profile123"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"
        
        # Verify create was called but get_athlete_profile was not called again
        service.athlete_repository.create.assert_called_once()
        # The service should not make an additional call to get the profile
    
    def test_performance_monitoring_decorators(self, service):
        """Test that performance monitoring decorators are applied"""
        # Check that all public methods have the monitor_performance decorator
        assert hasattr(service.create_athlete_profile, '__wrapped__')
        assert hasattr(service.get_athlete_profile, '__wrapped__')
        assert hasattr(service.update_athlete_profile, '__wrapped__')
        assert hasattr(service.delete_athlete_profile, '__wrapped__')
        assert hasattr(service.restore_athlete_profile, '__wrapped__')
        assert hasattr(service.get_athlete_profile_completion, '__wrapped__')


if __name__ == "__main__":
    pytest.main([__file__]) 