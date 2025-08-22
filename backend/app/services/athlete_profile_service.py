"""
Athlete Profile Service - Handles CRUD operations for athlete profiles
"""
from typing import Optional, Dict, Any, List
import logging
import re
import html
from datetime import datetime, timezone
from functools import lru_cache

from ..models.athlete import AthleteProfileCreate, AthleteProfileUpdate
from .database_service import DatabaseService, ResourceNotFoundError, DatabaseError, ValidationError
from .exceptions import (
    AthleteServiceError, ProfileCompletionError, AthleteValidationError,
    AthleteNotFoundError, SportCategoryError, InputValidationError, DataSanitizationError
)
from ..config.athlete_config import get_config
from ..utils.performance_monitor import monitor_performance

logger = logging.getLogger(__name__)


class AthleteProfileService:
    """Service for managing athlete profile CRUD operations"""
    
    def __init__(self, environment: str = None):
        self.config = get_config(environment)
        
        # Validate required config sections
        self._validate_config()
        
        # Initialize repositories
        self.collections = self.config['collections']
        self.athlete_repository = DatabaseService(self.collections["athlete_profiles"])
        self.user_repository = DatabaseService(self.collections["users"])
        self.user_profile_repository = DatabaseService(self.collections["user_profiles"])
        self.sport_category_repository = DatabaseService(self.collections["sport_categories"])
        
        # Get configuration values with defaults
        self.field_weights = self.config['field_weights']
        self.field_categories = self.config['field_categories']
        self.security_config = self.config.get('security', {})
        self.logging_config = self.config.get('logging', {})
        
        # Set security defaults
        self.security_config.setdefault('enable_input_validation', True)
        self.security_config.setdefault('enable_sanitization', True)
        self.security_config.setdefault('max_string_length', 1000)
        self.security_config.setdefault('allowed_genders', ['male', 'female', 'other'])
        self.security_config.setdefault('enable_rate_limiting', True)
        self.security_config.setdefault('max_requests_per_minute', 100)
        
        # Set logging defaults
        self.logging_config.setdefault('log_profile_updates', True)
        self.logging_config.setdefault('log_level', 'INFO')
    
    def _validate_config(self) -> None:
        """Validate required configuration sections exist"""
        required_sections = ['collections', 'field_weights', 'field_categories', 'security', 'logging']
        missing_sections = [section for section in required_sections if section not in self.config]
        
        if missing_sections:
            raise ValueError(f"Missing required config sections: {missing_sections}")
        
        # Validate collections
        required_collections = ["athlete_profiles", "users", "user_profiles", "sport_categories"]
        missing_collections = [coll for coll in required_collections if coll not in self.config['collections']]
        
        if missing_collections:
            raise ValueError(f"Missing required collections in config: {missing_collections}")
    
    @monitor_performance("create_athlete_profile")
    async def create_athlete_profile(self, user_id: str, profile_data: AthleteProfileCreate) -> Dict[str, Any]:
        """Create athlete profile with comprehensive validation"""
        try:
            # Input validation and sanitization
            if self.security_config['enable_input_validation']:
                self._validate_create_input(user_id, profile_data)
            
            if self.security_config['enable_sanitization']:
                profile_data = self._sanitize_profile_data(profile_data)
            
            # Validate user exists
            user = await self.user_repository.get_by_id(user_id)
            if not user:
                raise AthleteNotFoundError(f"User {user_id} not found")
            
            # Check if profile already exists
            existing_profile = await self.athlete_repository.get_by_field("user_id", user_id)
            if existing_profile:
                raise AthleteValidationError("Athlete profile already exists")
            
            # Validate sport category exists
            if not await self._validate_sport_category(profile_data.primary_sport_category_id):
                raise SportCategoryError(f"Invalid sport category: {profile_data.primary_sport_category_id}")
            
            # Create athlete profile
            profile_doc = self._prepare_profile_document(user_id, profile_data)
            profile_id = await self.athlete_repository.create(profile_doc)
            
            if self.logging_config['log_profile_updates']:
                logger.info(f"Created athlete profile {profile_id} for user {user_id}")
            
            # Update user profile completion
            await self._update_profile_completion(user_id)
            
            # Return the created document directly instead of fetching again
            profile_doc['id'] = profile_id
            return self._format_profile_document(profile_doc)
            
        except (AthleteServiceError, ValidationError, DatabaseError) as e:
            logger.error(f"Error creating athlete profile for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to create athlete profile: {str(e)}")
    
    @monitor_performance("get_athlete_profile")
    async def get_athlete_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get athlete profile by user ID"""
        try:
            profile_doc = await self.athlete_repository.get_by_field("user_id", user_id)
            if not profile_doc:
                return None
            
            return self._format_profile_document(profile_doc)
            
        except DatabaseError as e:
            logger.error(f"Database error getting athlete profile for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to get athlete profile: {str(e)}")
    
    @monitor_performance("update_athlete_profile")
    async def update_athlete_profile(self, user_id: str, profile_data: AthleteProfileUpdate) -> Dict[str, Any]:
        """Update athlete profile with validation"""
        try:
            # Input validation and sanitization
            if self.security_config['enable_input_validation']:
                self._validate_update_input(user_id, profile_data)
            
            if self.security_config['enable_sanitization']:
                profile_data = self._sanitize_update_data(profile_data)
            
            # Validate user exists
            user = await self.user_repository.get_by_id(user_id)
            if not user:
                raise AthleteNotFoundError(f"User {user_id} not found")
            
            # Prepare update data
            update_data = self._prepare_update_data(profile_data)
            if not update_data:
                return await self.get_athlete_profile(user_id)
            
            # Add updated timestamp
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Update profile directly using user_id field
            await self.athlete_repository.update_by_field("user_id", user_id, update_data)
            
            if self.logging_config['log_profile_updates']:
                logger.info(f"Updated athlete profile for user {user_id}")
            
            # Update profile completion
            await self._update_profile_completion(user_id)
            
            return await self.get_athlete_profile(user_id)
            
        except (AthleteServiceError, ResourceNotFoundError, DatabaseError) as e:
            logger.error(f"Error updating athlete profile for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to update athlete profile: {str(e)}")
    
    @monitor_performance("delete_athlete_profile")
    async def delete_athlete_profile(self, user_id: str) -> bool:
        """Soft delete athlete profile by marking as inactive"""
        try:
            profile_doc = await self.athlete_repository.get_by_field("user_id", user_id)
            if not profile_doc:
                return False
            
            # Soft delete by marking as inactive instead of hard delete
            update_data = {
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.athlete_repository.update(profile_doc["id"], update_data)
            
            if self.logging_config['log_profile_updates']:
                logger.info(f"Soft deleted athlete profile for user {user_id}")
            
            # Update user profile completion
            await self._update_profile_completion(user_id)
            
            return True
            
        except DatabaseError as e:
            logger.error(f"Database error deleting athlete profile for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to delete athlete profile: {str(e)}")
    
    @monitor_performance("restore_athlete_profile")
    async def restore_athlete_profile(self, user_id: str) -> bool:
        """Restore a soft-deleted athlete profile"""
        try:
            profile_doc = await self.athlete_repository.get_by_field("user_id", user_id)
            if not profile_doc:
                return False
            
            # Restore by marking as active
            update_data = {
                "is_active": True,
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.athlete_repository.update(profile_doc["id"], update_data)
            
            if self.logging_config['log_profile_updates']:
                logger.info(f"Restored athlete profile for user {user_id}")
            
            # Update profile completion
            await self._update_profile_completion(user_id)
            
            return True
            
        except DatabaseError as e:
            logger.error(f"Database error restoring athlete profile for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error restoring athlete profile for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to restore athlete profile: {str(e)}")
    
    @monitor_performance("get_athlete_profile_completion")
    async def get_athlete_profile_completion(self, user_id: str) -> Dict[str, Any]:
        """Get detailed profile completion information"""
        try:
            profile_doc = await self.athlete_repository.get_by_field("user_id", user_id)
            if not profile_doc:
                raise AthleteNotFoundError("Athlete profile not found")
            
            # Calculate completion by category
            category_completion = self._calculate_category_completion(profile_doc)
            
            # Calculate overall completion
            overall_percentage = self._calculate_completion_percentage(profile_doc)
            
            # Get missing fields
            missing_fields = self._get_missing_fields(profile_doc)
            
            return {
                "overall_completion": overall_percentage,
                "category_completion": category_completion,
                "missing_fields": missing_fields,
                "filled_fields": len(self.field_weights) - len(missing_fields),
                "total_fields": len(self.field_weights)
            }
            
        except (AthleteNotFoundError, DatabaseError) as e:
            logger.error(f"Error getting profile completion for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting profile completion for user {user_id}: {e}")
            raise AthleteServiceError(f"Failed to get profile completion: {str(e)}")
    
    # Private helper methods
    
    def _validate_create_input(self, user_id: str, profile_data: AthleteProfileCreate) -> None:
        """Validate input data for profile creation"""
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise InputValidationError("Invalid user_id")
        
        if not hasattr(profile_data, 'first_name') or not profile_data.first_name or not profile_data.first_name.strip():
            raise InputValidationError("first_name is required and cannot be empty")
        
        if len(profile_data.first_name.strip()) > self.security_config['max_string_length']:
            raise InputValidationError("first_name too long")
        
        if not hasattr(profile_data, 'last_name') or not profile_data.last_name or not profile_data.last_name.strip():
            raise InputValidationError("last_name is required and cannot be empty")
        
        if len(profile_data.last_name.strip()) > self.security_config['max_string_length']:
            raise InputValidationError("last_name too long")
        
        if not hasattr(profile_data, 'gender') or profile_data.gender not in self.security_config['allowed_genders']:
            raise InputValidationError(f"Invalid gender. Must be one of: {self.security_config['allowed_genders']}")
        
        if not hasattr(profile_data, 'primary_sport_category_id') or not profile_data.primary_sport_category_id:
            raise InputValidationError("primary_sport_category_id is required")
    
    def _validate_update_input(self, user_id: str, profile_data: AthleteProfileUpdate) -> None:
        """Validate input data for profile updates"""
        if not user_id or not isinstance(user_id, str) or not user_id.strip():
            raise InputValidationError("Invalid user_id")
        
        if hasattr(profile_data, 'first_name') and profile_data.first_name is not None:
            if not profile_data.first_name.strip():
                raise InputValidationError("first_name cannot be empty if provided")
            if len(profile_data.first_name.strip()) > self.security_config['max_string_length']:
                raise InputValidationError("first_name too long")
        
        if hasattr(profile_data, 'last_name') and profile_data.last_name is not None:
            if not profile_data.last_name.strip():
                raise InputValidationError("last_name cannot be empty if provided")
            if len(profile_data.last_name.strip()) > self.security_config['max_string_length']:
                raise InputValidationError("last_name too long")
        
        if hasattr(profile_data, 'gender') and profile_data.gender is not None:
            if profile_data.gender not in self.security_config['allowed_genders']:
                raise InputValidationError(f"Invalid gender. Must be one of: {self.security_config['allowed_genders']}")
    
    def _sanitize_profile_data(self, profile_data: AthleteProfileCreate) -> AthleteProfileCreate:
        """Sanitize profile data to prevent injection attacks"""
        try:
            # Create a sanitized copy
            sanitized_data = profile_data.model_copy()
            
            # Sanitize string fields
            if sanitized_data.first_name:
                sanitized_data.first_name = self._sanitize_string(sanitized_data.first_name)
            if sanitized_data.last_name:
                sanitized_data.last_name = self._sanitize_string(sanitized_data.last_name)
            if sanitized_data.location:
                sanitized_data.location = self._sanitize_string(sanitized_data.location)
            if sanitized_data.position:
                sanitized_data.position = self._sanitize_string(sanitized_data.position)
            if sanitized_data.academic_info:
                sanitized_data.academic_info = self._sanitize_string(sanitized_data.academic_info)
            if sanitized_data.career_highlights:
                sanitized_data.career_highlights = self._sanitize_string(sanitized_data.career_highlights)
            
            return sanitized_data
            
        except Exception as e:
            raise DataSanitizationError(f"Failed to sanitize profile data: {str(e)}")
    
    def _sanitize_update_data(self, profile_data: AthleteProfileUpdate) -> AthleteProfileUpdate:
        """Sanitize update data to prevent injection attacks"""
        try:
            # Create a sanitized copy
            sanitized_data = profile_data.model_copy()
            
            # Sanitize string fields that are not None
            if sanitized_data.first_name is not None:
                sanitized_data.first_name = self._sanitize_string(sanitized_data.first_name)
            if sanitized_data.last_name is not None:
                sanitized_data.last_name = self._sanitize_string(sanitized_data.last_name)
            if sanitized_data.location is not None:
                sanitized_data.location = self._sanitize_string(sanitized_data.location)
            if sanitized_data.position is not None:
                sanitized_data.position = self._sanitize_string(sanitized_data.position)
            if sanitized_data.academic_info is not None:
                sanitized_data.academic_info = self._sanitize_string(sanitized_data.academic_info)
            if sanitized_data.career_highlights is not None:
                sanitized_data.career_highlights = self._sanitize_string(sanitized_data.career_highlights)
            
            return sanitized_data
            
        except Exception as e:
            raise DataSanitizationError(f"Failed to sanitize update data: {str(e)}")
    
    def _sanitize_string(self, value: str) -> str:
        """Enhanced string sanitization with HTML escaping and pattern removal"""
        if not isinstance(value, str):
            return value
        
        # HTML escape to prevent XSS
        sanitized = html.escape(value)
        
        # Remove script-like patterns
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'vbscript:', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'data:', '', sanitized, flags=re.IGNORECASE)
        
        # Remove other potentially dangerous patterns
        sanitized = re.sub(r'<iframe[^>]*>.*?</iframe>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<object[^>]*>.*?</object>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<embed[^>]*>.*?</embed>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Limit length
        max_length = self.security_config.get('max_string_length', 1000)
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    def _prepare_profile_document(self, user_id: str, profile_data: AthleteProfileCreate) -> Dict[str, Any]:
        """Prepare profile document for creation"""
        return {
            "user_id": user_id,
            "first_name": profile_data.first_name,
            "last_name": profile_data.last_name,
            "date_of_birth": profile_data.date_of_birth.isoformat(),
            "gender": profile_data.gender,
            "location": profile_data.location,
            "primary_sport_category_id": profile_data.primary_sport_category_id,
            "secondary_sport_category_ids": profile_data.secondary_sport_category_ids or [],
            "position": profile_data.position,
            "height_cm": profile_data.height_cm,
            "weight_kg": profile_data.weight_kg,
            "academic_info": profile_data.academic_info,
            "career_highlights": profile_data.career_highlights,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
    
    def _prepare_update_data(self, profile_data: AthleteProfileUpdate) -> Dict[str, Any]:
        """Prepare update data from profile update model"""
        update_data = {}
        
        if profile_data.first_name is not None:
            update_data["first_name"] = profile_data.first_name
        if profile_data.last_name is not None:
            update_data["last_name"] = profile_data.last_name
        if profile_data.date_of_birth is not None:
            update_data["date_of_birth"] = profile_data.date_of_birth.isoformat()
        if profile_data.gender is not None:
            update_data["gender"] = profile_data.gender
        if profile_data.location is not None:
            update_data["location"] = profile_data.location
        if profile_data.primary_sport_category_id is not None:
            update_data["primary_sport_category_id"] = profile_data.primary_sport_category_id
        if profile_data.secondary_sport_category_ids is not None:
            update_data["secondary_sport_category_ids"] = profile_data.secondary_sport_category_ids
        if profile_data.position is not None:
            update_data["position"] = profile_data.position
        if profile_data.height_cm is not None:
            update_data["height_cm"] = profile_data.height_cm
        if profile_data.weight_kg is not None:
            update_data["weight_kg"] = profile_data.weight_kg
        if profile_data.academic_info is not None:
            update_data["academic_info"] = profile_data.academic_info
        if profile_data.career_highlights is not None:
            update_data["career_highlights"] = profile_data.career_highlights
        if profile_data.profile_image_url is not None:
            update_data["profile_image_url"] = profile_data.profile_image_url
        
        return update_data
    
    def _format_profile_document(self, profile_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Format profile document for response"""
        # Convert date string back to date object
        if "date_of_birth" in profile_doc:
            try:
                profile_doc["date_of_birth"] = datetime.fromisoformat(profile_doc["date_of_birth"]).date()
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid date format in profile {profile_doc.get('id')}: {e}")
                profile_doc["date_of_birth"] = None
        
        return profile_doc
    
    def _calculate_completion_percentage(self, profile_doc: Dict[str, Any]) -> int:
        """Calculate profile completion percentage"""
        total_weight = sum(self.field_weights.values())
        filled_weight = sum(
            self.field_weights[field] for field, value in profile_doc.items() 
            if field in self.field_weights and value is not None and value != ""
        )
        
        return int((filled_weight / total_weight) * 100) if total_weight > 0 else 0
    
    def _calculate_category_completion(self, profile_doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Calculate completion by category"""
        category_completion = {}
        for category, fields in self.field_categories.items():
            filled_fields = sum(1 for field in fields if profile_doc.get(field) and profile_doc[field] != "")
            category_completion[category] = {
                "completed": filled_fields,
                "total": len(fields),
                "percentage": int((filled_fields / len(fields)) * 100) if fields else 0
            }
        
        return category_completion
    
    def _get_missing_fields(self, profile_doc: Dict[str, Any]) -> List[str]:
        """Get list of missing fields"""
        return [
            field for field, value in profile_doc.items() 
            if field in self.field_weights and (value is None or value == "")
        ]
    
    @lru_cache(maxsize=100)
    async def _get_sport_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get sport category with caching to improve performance"""
        try:
            return await self.sport_category_repository.get_by_id(category_id)
        except DatabaseError as e:
            logger.error(f"Database error getting sport category {category_id}: {e}")
            return None
    
    async def _validate_sport_category(self, category_id: str) -> bool:
        """Validate sport category exists"""
        try:
            category = await self._get_sport_category(category_id)
            
            if not category:
                logger.warning(f"Sport category {category_id} not found")
                return False
            
            # Check if the category is active
            if category.get("is_active", True) is False:
                logger.warning(f"Sport category {category_id} is inactive")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error validating sport category {category_id}: {e}")
            return False
    
    async def _update_profile_completion(self, user_id: str) -> None:
        """Update athlete profile completion percentage with weighted scoring"""
        try:
            profile_doc = await self.athlete_repository.get_by_field("user_id", user_id)
            if not profile_doc:
                return
            
            completion_percentage = self._calculate_completion_percentage(profile_doc)
            
            # Update user profile completion
            await self.user_profile_repository.update(user_id, {"profile_completion": completion_percentage})
            
        except DatabaseError as e:
            logger.error(f"Database error updating profile completion for user {user_id}: {e}")
            raise ProfileCompletionError(f"Failed to update profile completion: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating profile completion for user {user_id}: {e}")
            raise ProfileCompletionError(f"Failed to update profile completion: {str(e)}") 