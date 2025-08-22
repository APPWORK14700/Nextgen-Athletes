from typing import Optional, Dict, Any, List, Union
import logging
import asyncio
from datetime import datetime, timedelta
from functools import lru_cache

from ..models.user import User, UserProfile, UserSettings, UserUpdate
from ..models.base import PaginatedResponse
from ..api.exceptions import (
    UserNotFoundError, UserAlreadyExistsError, InvalidUserDataError, 
    UserProfileNotFoundError, ValidationException, AuthorizationError
)
from .database_service import DatabaseService
from .metrics_service import metrics_service, MetricType
from ..utils.input_sanitizer import InputSanitizer
from ..utils.performance_monitor import monitor_performance
from ..utils.constants import (
    CACHE_CONFIG, USER_VALIDATION, PAGINATION, 
    ERROR_MESSAGES, SUCCESS_MESSAGES, SEARCH
)
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)

# Cache configuration from constants
MAX_CACHE_SIZE = CACHE_CONFIG["MAX_SIZE"]
CACHE_TTL_MINUTES = CACHE_CONFIG["TTL_MINUTES"]

class UserService:
    """Enhanced user service for managing user profiles and settings with caching and validation"""
    
    def __init__(self):
        self.user_service = DatabaseService("users")
        self.user_profile_service = DatabaseService("user_profiles")
        self.user_blocks_service = DatabaseService("user_blocks")
        self.user_reports_service = DatabaseService("user_reports")
        self.user_activity_service = DatabaseService("user_activity")
        self._cache = {}
        self._cache_lock = asyncio.Lock()
        self._cache_ttl = timedelta(minutes=CACHE_TTL_MINUTES)
        
        # Initialize metrics
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize service-specific metrics"""
        metrics_service.register_metric("user_cache_hit", MetricType.COUNTER, "Number of cache hits")
        metrics_service.register_metric("user_cache_miss", MetricType.COUNTER, "Number of cache misses")
        metrics_service.register_metric("user_database_queries", MetricType.COUNTER, "Number of database queries")
        metrics_service.register_metric("user_validation_errors", MetricType.COUNTER, "Number of validation errors")
    
    async def _get_cached_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from cache if available and not expired"""
        if user_id in self._cache:
            cached_data, timestamp = self._cache[user_id]
            if datetime.now() - timestamp < self._cache_ttl:
                metrics_service.increment("user_cache_hit")
                return cached_data
            else:
                # Remove expired cache entry
                del self._cache[user_id]
        
        metrics_service.increment("user_cache_miss")
        return None
    
    async def _set_cached_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """
        Cache user data with timestamp and size management.
        
        Automatically manages cache size by removing oldest entries when the cache
        reaches its maximum size limit. Uses constants for configuration.
        
        Args:
            user_id: Unique identifier for the user
            user_data: User data dictionary to cache
        """
        async with self._cache_lock:
            # Check cache size and remove oldest entries if needed
            if len(self._cache) >= MAX_CACHE_SIZE:
                # Remove oldest entries to get cache below limit
                remove_count = len(self._cache) - MAX_CACHE_SIZE + 1
                oldest_entries = sorted(
                    self._cache.items(), 
                    key=lambda x: x[1][1]
                )[:remove_count]
                
                for key, _ in oldest_entries:
                    del self._cache[key]
                
                logger.info(f"Cache size limit reached. Removed {remove_count} oldest entries.")
            
            self._cache[user_id] = (user_data, datetime.now())
    
    async def _invalidate_user_cache(self, user_id: str) -> None:
        """
        Invalidate user cache entry.
        
        Removes a specific user from the cache, typically called after
        user data updates to ensure cache consistency.
        
        Args:
            user_id: Unique identifier for the user to remove from cache
        """
        async with self._cache_lock:
            if user_id in self._cache:
                del self._cache[user_id]
    
    async def _fetch_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user data from database.
        
        Retrieves user data from the users collection and combines it with
        profile data from the user_profiles collection. Increments database
        query metrics for monitoring.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Combined user and profile data dictionary, or None if not found
            
        Raises:
            Exception: If database query fails
        """
        try:
            metrics_service.increment("user_database_queries")
            user_doc = await self.user_service.get_by_id(user_id)
            if not user_doc:
                return None
            
            # Get user profile
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_id)
            
            # Combine user and profile data
            result = {**user_doc}
            if profile_doc:
                result.update(profile_doc)
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
            raise
    
    @monitor_performance("get_user_by_id")
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by ID with intelligent caching.
        
        Retrieves user data by ID, checking the cache first for performance.
        If not in cache, fetches from database and caches the result.
        Includes comprehensive input validation and error handling.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Complete user data dictionary including profile information, or None if not found
            
        Raises:
            InvalidUserDataError: If user_id is invalid or missing
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate input using constants
            if not user_id or not isinstance(user_id, str):
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["REQUIRED_FIELD"].format(field="user_id"))
            
            # Check cache first
            cached_user = await self._get_cached_user(user_id)
            if cached_user:
                return cached_user
            
            # Fetch from database
            user_data = await self._fetch_user_by_id(user_id)
            if not user_data:
                raise UserNotFoundError(user_id)
            
            # Cache the result
            await self._set_cached_user(user_id, user_data)
            
            return user_data
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            raise
    
    @monitor_performance("get_user_by_email")
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email address with validation and sanitization.
        
        Retrieves user data by email address, applying comprehensive email
        validation and sanitization. Combines user and profile data for
        complete user information.
        
        Args:
            email: Email address to search for
            
        Returns:
            Complete user data dictionary including profile information, or None if not found
            
        Raises:
            InvalidUserDataError: If email format is invalid
            Exception: For other unexpected errors
        """
        try:
            # Sanitize and validate email using constants
            sanitized_email = InputSanitizer.sanitize_email(email)
            
            metrics_service.increment("user_database_queries")
            user_doc = await self.user_service.get_by_field("email", sanitized_email)
            if not user_doc:
                return None
            
            # Get user profile
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_doc["id"])
            
            # Combine user and profile data
            result = {**user_doc}
            if profile_doc:
                result.update(profile_doc)
            
            return result
            
        except ValueError as e:
            metrics_service.increment("user_validation_errors")
            raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="email"))
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            raise
    
    @monitor_performance("get_user_by_username")
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username with validation and sanitization.
        
        Retrieves user data by username, applying comprehensive username
        validation and sanitization. Combines user and profile data for
        complete user information.
        
        Args:
            username: Username to search for
            
        Returns:
            Complete user data dictionary including profile information, or None if not found
            
        Raises:
            InvalidUserDataError: If username format is invalid
            Exception: For other unexpected errors
        """
        try:
            # Sanitize and validate username using constants
            sanitized_username = InputSanitizer.sanitize_username(username)
            
            metrics_service.increment("user_database_queries")
            profile_doc = await self.user_profile_service.get_by_field("username", sanitized_username)
            if not profile_doc:
                return None
            
            # Get user data
            user_doc = await self.user_service.get_by_id(profile_doc["user_id"])
            if not user_doc:
                return None
            
            # Combine user and profile data
            result = {**user_doc}
            result.update(profile_doc)
            
            return result
            
        except ValueError as e:
            metrics_service.increment("user_validation_errors")
            raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="username"))
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            raise
    
    @monitor_performance("update_user_profile")
    async def update_user_profile(self, user_id: str, profile_data: UserUpdate) -> Dict[str, Any]:
        """
        Update user profile with comprehensive validation and sanitization.
        
        Updates user profile information including username, phone number, and settings.
        Applies comprehensive input validation, sanitization, and business logic checks.
        Automatically invalidates cache after successful updates.
        
        Args:
            user_id: Unique identifier for the user to update
            profile_data: Profile data object containing fields to update
            
        Returns:
            Updated user data dictionary with all current information
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            UserAlreadyExistsError: If username is already taken by another user
            InvalidUserDataError: If input validation fails
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate and sanitize input data
            update_data = {}
            
            if profile_data.username is not None:
                try:
                    sanitized_username = InputSanitizer.sanitize_username(profile_data.username)
                    update_data["username"] = sanitized_username
                    
                    # Check if username is already taken by another user
                    existing_user = await self.get_user_by_username(sanitized_username)
                    if existing_user and existing_user["id"] != user_id:
                        raise UserAlreadyExistsError("username", sanitized_username)
                except ValueError as e:
                    metrics_service.increment("user_validation_errors")
                    raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="username"))
            
            if profile_data.phone_number is not None:
                try:
                    sanitized_phone = InputSanitizer.sanitize_phone_number(profile_data.phone_number)
                    update_data["phone_number"] = sanitized_phone
                except ValueError as e:
                    metrics_service.increment("user_validation_errors")
                    raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="phone_number"))
            
            if profile_data.settings is not None:
                update_data["settings"] = profile_data.settings.dict()
            
            if update_data:
                await self.user_profile_service.update(user_id, update_data)
                # Invalidate cache
                await self._invalidate_user_cache(user_id)
            
            # Get updated user data
            return await self.get_user_by_id(user_id)
            
        except (UserNotFoundError, UserAlreadyExistsError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error updating user profile {user_id}: {e}")
            raise
    
    @monitor_performance("update_user_settings")
    async def update_user_settings(self, user_id: str, settings: UserSettings) -> Dict[str, Any]:
        """
        Update user settings with validation.
        
        Updates user settings while ensuring data integrity and validation.
        Automatically invalidates cache after successful updates.
        
        Args:
            user_id: Unique identifier for the user to update
            settings: UserSettings object containing new settings
            
        Returns:
            Updated user data dictionary with current settings
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            InvalidUserDataError: If settings format is invalid
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate settings
            if not isinstance(settings, UserSettings):
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="settings"))
            
            await self.user_profile_service.update(user_id, {"settings": settings.dict()})
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            # Get updated user data
            return await self.get_user_by_id(user_id)
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error updating user settings {user_id}: {e}")
            raise
    
    @monitor_performance("get_user_settings")
    async def get_user_settings(self, user_id: str) -> UserSettings:
        """
        Get user settings with default fallback.
        
        Retrieves user settings from the profile collection. If no settings
        exist, returns default UserSettings object. This method ensures
        users always have valid settings even if none were previously saved.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            UserSettings object with current or default settings
            
        Raises:
            Exception: If database query fails
        """
        try:
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_id)
            if not profile_doc or "settings" not in profile_doc:
                return UserSettings()
            
            return UserSettings(**profile_doc["settings"])
            
        except Exception as e:
            logger.error(f"Error getting user settings {user_id}: {e}")
            raise
    
    @monitor_performance("update_profile_completion")
    async def update_profile_completion(self, user_id: str, completion_percentage: int) -> bool:
        """
        Update user profile completion percentage with validation.
        
        Updates the profile completion percentage for a user, ensuring the value
        is within valid range (0-100). Automatically invalidates cache after
        successful updates to maintain data consistency.
        
        Args:
            user_id: Unique identifier for the user to update
            completion_percentage: Integer value between 0 and 100 representing completion
            
        Returns:
            True if update was successful
            
        Raises:
            InvalidUserDataError: If completion percentage is outside valid range
            Exception: For other unexpected errors
        """
        try:
            # Validate completion percentage
            if not 0 <= completion_percentage <= 100:
                raise InvalidUserDataError("Profile completion must be between 0 and 100")
            
            await self.user_profile_service.update(
                user_id, 
                {"profile_completion": completion_percentage}
            )
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            return True
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error updating profile completion {user_id}: {e}")
            raise
    
    @monitor_performance("get_users_by_role")
    async def get_users_by_role(self, role: str, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        """
        Get users by role with pagination and validation.
        
        Retrieves a paginated list of users filtered by role. Applies comprehensive
        validation for role and pagination parameters. Uses constants for validation limits.
        
        Args:
            role: User role to filter by (athlete, scout, admin)
            limit: Maximum number of users to return (1-1000)
            offset: Number of users to skip for pagination
            
        Returns:
            PaginatedResponse object containing users and pagination metadata
            
        Raises:
            InvalidUserDataError: If role or pagination parameters are invalid
            Exception: For other unexpected errors
        """
        try:
            # Validate and sanitize role
            try:
                sanitized_role = InputSanitizer.validate_role(role)
            except ValueError as e:
                metrics_service.increment("user_validation_errors")
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="role"))
            
            # Validate pagination parameters using constants
            if limit < PAGINATION["MIN_LIMIT"] or limit > PAGINATION["MAX_LIMIT"]:
                raise InvalidUserDataError(
                    ERROR_MESSAGES["VALIDATION"]["TOO_LONG"].format(
                        field="limit", 
                        max_length=PAGINATION["MAX_LIMIT"]
                    )
                )
            if offset < PAGINATION["MIN_OFFSET"]:
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["TOO_SHORT"].format(field="offset", min_length=0))
            
            filters = [FieldFilter("role", "==", sanitized_role)]
            
            metrics_service.increment("user_database_queries")
            users = await self.user_service.query(filters, limit, offset)
            total_count = await self.user_service.count(filters)
            
            return PaginatedResponse(
                count=total_count,
                results=users,
                next=f"?limit={limit}&offset={offset + limit}" if offset + limit < total_count else None,
                previous=f"?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
            )
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting users by role {role}: {e}")
            raise
    
    @monitor_performance("get_users_by_status")
    async def get_users_by_status(self, status: str, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        """
        Get users by status with pagination and validation.
        
        Retrieves a paginated list of users filtered by status. Applies comprehensive
        validation for status and pagination parameters. Uses constants for validation limits.
        
        Args:
            status: User status to filter by (active, suspended, deleted)
            limit: Maximum number of users to return (1-1000)
            offset: Number of users to skip for pagination
            
        Returns:
            PaginatedResponse object containing users and pagination metadata
            
        Raises:
            InvalidUserDataError: If status or pagination parameters are invalid
            Exception: For other unexpected errors
        """
        try:
            # Validate and sanitize status
            try:
                sanitized_status = InputSanitizer.validate_status(status)
            except ValueError as e:
                metrics_service.increment("user_validation_errors")
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="status"))
            
            # Validate pagination parameters using constants
            if limit < PAGINATION["MIN_LIMIT"] or limit > PAGINATION["MAX_LIMIT"]:
                raise InvalidUserDataError(
                    ERROR_MESSAGES["VALIDATION"]["TOO_LONG"].format(
                        field="limit", 
                        max_length=PAGINATION["MAX_LIMIT"]
                    )
                )
            if offset < PAGINATION["MIN_OFFSET"]:
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["TOO_SHORT"].format(field="offset", min_length=0))
            
            filters = [FieldFilter("status", "==", sanitized_status)]
            
            metrics_service.increment("user_database_queries")
            users = await self.user_service.query(filters, limit, offset)
            total_count = await self.user_service.count(filters)
            
            return PaginatedResponse(
                count=total_count,
                results=users,
                next=f"?limit={limit}&offset={offset + limit}" if offset + limit < total_count else None,
                previous=f"?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
            )
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting users by status {status}: {e}")
            raise
    
    @monitor_performance("update_user_status")
    async def update_user_status(self, user_id: str, status: str, reason: Optional[str] = None) -> bool:
        """
        Update user status with comprehensive validation and sanitization.
        
        Updates the status of a user account (active, suspended, deleted) with
        optional reason. Applies comprehensive validation, sanitization, and
        automatically invalidates cache after successful updates.
        
        Args:
            user_id: Unique identifier for the user to update
            status: New status value (active, suspended, deleted)
            reason: Optional reason for status change (sanitized and limited)
            
        Returns:
            True if status update was successful
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            InvalidUserDataError: If status or reason validation fails
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate and sanitize status
            try:
                sanitized_status = InputSanitizer.validate_status(status)
            except ValueError as e:
                metrics_service.increment("user_validation_errors")
                raise InvalidUserDataError(f"Invalid status: {e}")
            
            # Sanitize reason if provided using constants
            sanitized_reason = None
            if reason:
                sanitized_reason = InputSanitizer.sanitize_text(
                    reason, 
                    max_length=USER_VALIDATION["TEXT_FIELDS"]["REASON_MAX_LENGTH"]
                )
            
            update_data = {"status": sanitized_status}
            if sanitized_reason:
                update_data["status_reason"] = sanitized_reason
                update_data["status_updated_at"] = datetime.utcnow()
            
            await self.user_service.update(user_id, update_data)
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            return True
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error updating user status {user_id}: {e}")
            raise
    
    @monitor_performance("search_users_optimized")
    async def search_users_optimized(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Optimized user search with proper indexing and deduplication.
        
        Performs efficient user search using Firestore's built-in indexing capabilities.
        Searches both email and username fields with prefix matching for optimal performance.
        Applies comprehensive input sanitization and validation using constants.
        
        Args:
            query: Search query string to match against emails and usernames
            limit: Maximum number of results to return
            
        Returns:
            List of user dictionaries matching the search criteria
            
        Raises:
            InvalidUserDataError: If search query is empty or invalid
            Exception: For other unexpected errors
        """
        try:
            # Sanitize search query using constants
            sanitized_query = InputSanitizer.sanitize_search_query(
                query, 
                max_length=SEARCH["MAX_QUERY_LENGTH"]
            )
            
            if not sanitized_query:
                raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["REQUIRED_FIELD"].format(field="search query"))
            
            # Use Firestore's built-in search with proper indexing
            # Search by email prefix
            email_filters = [
                FieldFilter("email", ">=", sanitized_query),
                FieldFilter("email", "<=", sanitized_query + "\uf8ff")
            ]
            
            metrics_service.increment("user_database_queries")
            email_users = await self.user_service.query(email_filters, limit)
            
            # Search by username prefix
            username_filters = [
                FieldFilter("username", ">=", sanitized_query),
                FieldFilter("username", "<=", sanitized_query + "\uf8ff")
            ]
            
            username_users = await self.user_profile_service.query(username_filters, limit)
            
            # Merge results efficiently
            return await self._merge_search_results(email_users, username_users, limit)
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            raise
    
    async def _merge_search_results(self, email_users: List[Dict], username_users: List[Dict], limit: int) -> List[Dict[str, Any]]:
        """
        Merge search results efficiently.
        
        Combines results from email and username searches, removing duplicates
        and ensuring data consistency. Optimized for performance with minimal
        database calls.
        
        Args:
            email_users: List of users found by email search
            username_users: List of users found by username search
            limit: Maximum number of results to return
            
        Returns:
            Merged and deduplicated list of user results
            
        Raises:
            Exception: If merging process fails
        """
        try:
            # Create a map of user_id to user data
            user_map = {}
            
            # Add email search results
            for user in email_users:
                user_map[user["id"]] = user
            
            # Add username search results and combine with existing data
            for profile in username_users:
                user_id = profile["user_id"]
                if user_id in user_map:
                    # Update existing user with profile data
                    user_map[user_id].update(profile)
                else:
                    # Get full user data for this profile
                    user_data = await self.user_service.get_by_id(user_id)
                    if user_data:
                        user_data.update(profile)
                        user_map[user_id] = user_data
            
            # Convert back to list and limit results
            results = list(user_map.values())
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error merging search results: {e}")
            raise
    
    @monitor_performance("get_user_analytics")
    async def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """
        Enhanced user analytics with comprehensive data and role-based insights.
        
        Retrieves comprehensive analytics for a user including profile completion,
        account age, verification status, and role-specific metrics. Provides
        valuable insights for user engagement and platform optimization.
        
        Args:
            user_id: Unique identifier for the user to analyze
            
        Returns:
            Dictionary containing comprehensive user analytics including:
            - profile_completion: Profile completion percentage (0-100)
            - last_login: Timestamp of last login activity
            - is_verified: Account verification status
            - account_age_days: Age of account in days
            - status: Current account status
            - role: User role with specific analytics
            - Role-specific metrics (media count, opportunities, messages, etc.)
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Get profile data
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_id)
            
            # Basic analytics
            analytics = {
                "profile_completion": profile_doc.get("profile_completion", 0) if profile_doc else 0,
                "last_login": profile_doc.get("last_login") if profile_doc else None,
                "is_verified": profile_doc.get("is_verified", False) if profile_doc else False,
                "account_age_days": None,
                "status": user.get("status", "active"),
                "role": user.get("role", "athlete")
            }
            
            # Calculate account age
            if user.get("created_at"):
                try:
                    created_at = user["created_at"]
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    account_age = datetime.now(created_at.tzinfo) - created_at
                    analytics["account_age_days"] = account_age.days
                except Exception:
                    pass
            
            # Enhanced analytics based on role
            if user.get("role") == "athlete":
                # Add athlete-specific analytics
                analytics.update({
                    "media_count": 0,  # Would be fetched from media service
                    "opportunities_applied": 0,  # Would be fetched from opportunities service
                    "messages_sent": 0,  # Would be fetched from conversations service
                    "profile_views": 0  # Would be tracked separately
                })
            elif user.get("role") == "scout":
                # Add scout-specific analytics
                analytics.update({
                    "opportunities_created": 0,  # Would be fetched from opportunities service
                    "athletes_contacted": 0,  # Would be fetched from conversations service
                    "searches_performed": 0  # Would be tracked separately
                })
            
            return analytics
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting user analytics {user_id}: {e}")
            raise
    
    @monitor_performance("delete_user_account")
    async def delete_user_account(self, user_id: str) -> bool:
        """
        Soft delete user account with comprehensive validation.
        
        Performs a soft delete of a user account by updating status to 'deleted'
        and setting profile to inactive. This preserves data integrity while
        removing user access. Automatically invalidates cache after successful deletion.
        
        Args:
            user_id: Unique identifier for the user account to delete
            
        Returns:
            True if account deletion was successful
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Update user status to deleted
            await self.user_service.update(user_id, {"status": "deleted"})
            
            # Update profile to inactive
            await self.user_profile_service.update(user_id, {"is_active": False})
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            return True
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error deleting user account {user_id}: {e}")
            raise
    
    @monitor_performance("verify_user")
    async def verify_user(self, user_id: str) -> bool:
        """
        Verify user account with comprehensive validation.
        
        Marks a user account as verified, typically after identity verification
        or email confirmation. Updates the verification status in the user profile
        and automatically invalidates cache to ensure data consistency.
        
        Args:
            user_id: Unique identifier for the user to verify
            
        Returns:
            True if user verification was successful
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            await self.user_profile_service.update(user_id, {"is_verified": True})
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            return True
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error verifying user {user_id}: {e}")
            raise
    
    @monitor_performance("bulk_update_user_status")
    async def bulk_update_user_status(self, user_ids: List[str], status: str, reason: Optional[str] = None) -> bool:
        """
        Bulk update user status for admin operations with comprehensive validation.
        
        Updates the status of multiple users simultaneously, typically used for
        administrative operations. Applies comprehensive validation, sanitization,
        and automatically invalidates cache for all updated users.
        
        Args:
            user_ids: List of user IDs to update
            status: New status value for all users (active, suspended, deleted)
            reason: Optional reason for status change (sanitized and limited)
            
        Returns:
            True if bulk update was successful
            
        Raises:
            InvalidUserDataError: If status, user IDs, or reason validation fails
            Exception: For other unexpected errors
        """
        try:
            # Validate and sanitize status
            try:
                sanitized_status = InputSanitizer.validate_status(status)
            except ValueError as e:
                metrics_service.increment("user_validation_errors")
                raise InvalidUserDataError(f"Invalid status: {e}")
            
            # Validate user IDs
            if not user_ids:
                raise InvalidUserDataError("User IDs list cannot be empty")
            
            # Sanitize user IDs
            sanitized_user_ids = []
            for user_id in user_ids:
                if user_id and isinstance(user_id, str):
                    sanitized_user_ids.append(user_id.strip())
            
            if not sanitized_user_ids:
                raise InvalidUserDataError("No valid user IDs provided")
            
            # Sanitize reason if provided using constants
            sanitized_reason = None
            if reason:
                sanitized_reason = InputSanitizer.sanitize_text(
                    reason, 
                    max_length=USER_VALIDATION["TEXT_FIELDS"]["REASON_MAX_LENGTH"]
                )
            
            # Prepare updates
            updates = []
            for user_id in sanitized_user_ids:
                update_data = {"status": sanitized_status}
                if sanitized_reason:
                    update_data["status_reason"] = sanitized_reason
                    update_data["status_updated_at"] = datetime.utcnow()
                updates.append((user_id, update_data))
            
            # Perform bulk update
            success = await self.user_service.batch_update(updates)
            
            # Invalidate cache for all updated users
            for user_id in sanitized_user_ids:
                await self._invalidate_user_cache(user_id)
            
            return success
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error bulk updating user status: {e}")
            raise
    
    @monitor_performance("get_user_statistics")
    async def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive platform user statistics for admin dashboard.
        
        Retrieves aggregated statistics about users including counts by role,
        status, and verification status. This method provides essential metrics
        for administrative monitoring and decision-making.
        
        Args:
            None
            
        Returns:
            Dictionary containing comprehensive user statistics including:
            - total_users: Total number of users on the platform
            - by_role: Breakdown by user roles (athletes, scouts, admins)
            - by_status: Breakdown by account status (active, suspended, deleted)
            - verification: Verification statistics (verified vs unverified)
            
        Raises:
            Exception: If database queries fail
        """
        try:
            # Get counts by role
            athlete_count = await self.user_service.count([FieldFilter("role", "==", "athlete")])
            scout_count = await self.user_service.count([FieldFilter("role", "==", "scout")])
            admin_count = await self.user_service.count([FieldFilter("role", "==", "admin")])
            
            # Get counts by status
            active_count = await self.user_service.count([FieldFilter("status", "==", "active")])
            suspended_count = await self.user_service.count([FieldFilter("status", "==", "suspended")])
            deleted_count = await self.user_service.count([FieldFilter("status", "==", "deleted")])
            
            # Get verification statistics
            verified_count = await self.user_profile_service.count([FieldFilter("is_verified", "==", True)])
            
            return {
                "total_users": athlete_count + scout_count + admin_count,
                "by_role": {
                    "athletes": athlete_count,
                    "scouts": scout_count,
                    "admins": admin_count
                },
                "by_status": {
                    "active": active_count,
                    "suspended": suspended_count,
                    "deleted": deleted_count
                },
                "verification": {
                    "verified": verified_count,
                    "unverified": (athlete_count + scout_count + admin_count) - verified_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            raise
    
    async def cleanup_expired_cache(self) -> int:
        """
        Clean up expired cache entries.
        
        Removes cache entries that have exceeded their TTL (Time To Live).
        This method helps prevent memory leaks and maintains cache performance.
        Uses constants for cache configuration.
        
        Returns:
            Number of expired entries that were cleaned up
            
        Raises:
            Exception: If cleanup process fails
        """
        try:
            expired_count = 0
            current_time = datetime.now()
            
            async with self._cache_lock:
                expired_keys = [
                    key for key, (_, timestamp) in self._cache.items()
                    if current_time - timestamp > self._cache_ttl
                ]
                
                for key in expired_keys:
                    del self._cache[key]
                    expired_count += 1
            
            logger.info(f"Cleaned up {expired_count} expired cache entries")
            return expired_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Check service health and return status information.
        
        Provides comprehensive health information including cache status,
        database connectivity, and service metrics. Useful for monitoring
        and debugging purposes.
        
        Returns:
            Dictionary containing health status and metrics
        """
        try:
            # Check cache health
            cache_info = {
                "size": len(self._cache),
                "max_size": MAX_CACHE_SIZE,
                "ttl_minutes": CACHE_TTL_MINUTES,
                "status": "healthy" if len(self._cache) < MAX_CACHE_SIZE else "warning"
            }
            
            # Check database connectivity (simple test)
            try:
                # Test database connection with a simple count query
                test_count = await self.user_service.count([])
                db_status = "healthy"
            except Exception:
                db_status = "unhealthy"
            
            return {
                "status": "healthy" if db_status == "healthy" else "degraded",
                "timestamp": datetime.now().isoformat(),
                "cache": cache_info,
                "database": {
                    "status": db_status,
                    "collections": ["users", "user_profiles", "user_blocks", "user_reports", "user_activity"]
                },
                "service": {
                    "name": "UserService",
                    "version": "1.0.0",
                    "uptime": "active"
                }
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    # User blocking and reporting functionality
    @monitor_performance("block_user")
    async def block_user(self, user_id: str, blocked_user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Block a user with comprehensive validation and logging.
        
        Creates a block relationship between two users, preventing interaction.
        Applies business logic validation, input sanitization, and comprehensive
        logging. Uses constants for validation limits.
        
        Args:
            user_id: ID of the user performing the block action
            blocked_user_id: ID of the user being blocked
            reason: Optional reason for blocking (sanitized and limited)
            
        Returns:
            Dictionary containing block confirmation and blocked user details
            
        Raises:
            UserNotFoundError: If either user doesn't exist
            InvalidUserDataError: If blocking operation is invalid
            Exception: For other unexpected errors
        """
        try:
            # Validate both users exist
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            blocked_user = await self.get_user_by_id(blocked_user_id)
            if not blocked_user:
                raise UserNotFoundError(blocked_user_id)
            
            # Prevent self-blocking
            if user_id == blocked_user_id:
                raise InvalidUserDataError("Cannot block yourself")
            
            # Check if already blocked
            existing_block = await self._get_block_record(user_id, blocked_user_id)
            if existing_block:
                raise InvalidUserDataError("User is already blocked")
            
            # Sanitize reason if provided using constants
            sanitized_reason = None
            if reason:
                sanitized_reason = InputSanitizer.sanitize_text(
                    reason, 
                    max_length=USER_VALIDATION["TEXT_FIELDS"]["REASON_MAX_LENGTH"]
                )
            
            # Create block record
            block_data = {
                "user_id": user_id,
                "blocked_user_id": blocked_user_id,
                "reason": sanitized_reason,
                "created_at": datetime.utcnow()
            }
            
            block_id = await self._create_block_record(block_data)
            
            # Log activity
            await self._log_user_activity(
                user_id, 
                "block_user", 
                f"Blocked user {blocked_user.get('username', blocked_user_id)}",
                {"blocked_user_id": blocked_user_id, "reason": sanitized_reason}
            )
            
            return {
                "id": block_id,
                "message": SUCCESS_MESSAGES["USER"]["BLOCKED"],
                "blocked_user": {
                    "id": blocked_user_id,
                    "username": blocked_user.get("username"),
                    "blocked_at": block_data["created_at"]
                }
            }
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error blocking user {blocked_user_id} by {user_id}: {e}")
            raise

    @monitor_performance("unblock_user")
    async def unblock_user(self, user_id: str, blocked_user_id: str) -> Dict[str, Any]:
        """
        Unblock a previously blocked user with comprehensive validation.
        
        Removes the block relationship between two users, allowing them to
        interact again. Validates the existence of the block record and
        logs the unblock action for audit purposes.
        
        Args:
            user_id: ID of the user performing the unblock action
            blocked_user_id: ID of the user being unblocked
            
        Returns:
            Dictionary containing unblock confirmation message
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            InvalidUserDataError: If user is not currently blocked
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Check if block exists
            block_record = await self._get_block_record(user_id, blocked_user_id)
            if not block_record:
                raise InvalidUserDataError("User is not blocked")
            
            # Remove block record
            await self._remove_block_record(block_record["id"])
            
            # Log activity
            await self._log_user_activity(
                user_id, 
                "unblock_user", 
                f"Unblocked user {blocked_user_id}",
                {"blocked_user_id": blocked_user_id}
            )
            
            return {"message": "User unblocked successfully"}
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error unblocking user {blocked_user_id} by {user_id}: {e}")
            raise

    @monitor_performance("get_blocked_users")
    async def get_blocked_users(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get comprehensive list of users blocked by the specified user.
        
        Retrieves all users that have been blocked by a specific user, including
        block details such as blocking reason and timestamp. Provides complete
        information for user management and audit purposes.
        
        Args:
            user_id: ID of the user whose blocked users list to retrieve
            
        Returns:
            List of dictionaries containing blocked user information:
            - id: Blocked user's unique identifier
            - username: Blocked user's username
            - blocked_at: Timestamp when the block was created
            - reason: Optional reason for the block
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Get all block records for this user
            block_records = await self._get_user_block_records(user_id)
            
            # Get blocked user details
            blocked_users = []
            for block_record in block_records:
                blocked_user = await self.get_user_by_id(block_record["blocked_user_id"])
                if blocked_user:
                    blocked_users.append({
                        "id": blocked_user["id"],
                        "username": blocked_user.get("username"),
                        "blocked_at": block_record["created_at"],
                        "reason": block_record.get("reason")
                    })
            
            return blocked_users
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting blocked users for {user_id}: {e}")
            raise

    @monitor_performance("report_user")
    async def report_user(self, reporter_id: str, reported_user_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Report a user with comprehensive validation and sanitization.
        
        Creates a user report with detailed information including reason,
        description, and evidence. Applies comprehensive input validation,
        sanitization, and duplicate prevention. Uses constants for validation limits.
        
        Args:
            reporter_id: ID of the user making the report
            reported_user_id: ID of the user being reported
            report_data: Dictionary containing report details (reason, description, evidence_url)
            
        Returns:
            Dictionary containing report confirmation and status
            
        Raises:
            UserNotFoundError: If either user doesn't exist
            InvalidUserDataError: If report data is invalid or duplicate
            Exception: For other unexpected errors
        """
        try:
            # Validate both users exist
            reporter = await self.get_user_by_id(reporter_id)
            if not reporter:
                raise UserNotFoundError(reporter_id)
            
            reported_user = await self.get_user_by_id(reported_user_id)
            if not reported_user:
                raise UserNotFoundError(reported_user_id)
            
            # Prevent self-reporting
            if reporter_id == reported_user_id:
                raise InvalidUserDataError("Cannot report yourself")
            
            # Validate and sanitize report data using constants
            required_fields = ["reason"]
            for field in required_fields:
                if field not in report_data or not report_data[field]:
                    raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["REQUIRED_FIELD"].format(field=f"report {field}"))
            
            # Sanitize report data using constants
            sanitized_reason = InputSanitizer.sanitize_text(
                report_data["reason"], 
                max_length=USER_VALIDATION["TEXT_FIELDS"]["REASON_MAX_LENGTH"]
            )
            sanitized_description = None
            if "description" in report_data:
                sanitized_description = InputSanitizer.sanitize_text(
                    report_data["description"], 
                    max_length=USER_VALIDATION["TEXT_FIELDS"]["DESCRIPTION_MAX_LENGTH"]
                )
            
            sanitized_evidence_url = None
            if "evidence_url" in report_data:
                try:
                    sanitized_evidence_url = InputSanitizer.sanitize_url(report_data["evidence_url"])
                except ValueError as e:
                    raise InvalidUserDataError(ERROR_MESSAGES["VALIDATION"]["INVALID_FORMAT"].format(field="evidence URL"))
            
            # Check for duplicate reports (within 24 hours)
            recent_report = await self._get_recent_report(reporter_id, reported_user_id)
            if recent_report:
                raise InvalidUserDataError("You have already reported this user recently")
            
            # Create report record
            report_record = {
                "reporter_id": reporter_id,
                "reported_user_id": reported_user_id,
                "reason": sanitized_reason,
                "description": sanitized_description,
                "evidence_url": sanitized_evidence_url,
                "status": "pending",
                "created_at": datetime.utcnow()
            }
            
            report_id = await self._create_report_record(report_record)
            
            # Log activity
            await self._log_user_activity(
                reporter_id, 
                "report_user", 
                f"Reported user {reported_user.get('username', reported_user_id)} for {sanitized_reason}",
                {
                    "reported_user_id": reported_user_id,
                    "reason": sanitized_reason,
                    "report_id": report_id
                }
            )
            
            return {
                "id": report_id,
                "message": SUCCESS_MESSAGES["USER"]["REPORTED"],
                "status": "pending"
            }
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error reporting user {reported_user_id} by {reporter_id}: {e}")
            raise

    @monitor_performance("get_user_activity")
    async def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get comprehensive user activity log with fallback to profile data.
        
        Retrieves user activity from the dedicated activity collection, providing
        detailed audit trail of user actions. Falls back to basic profile-based
        activity if no dedicated records exist, ensuring comprehensive coverage.
        
        Args:
            user_id: Unique identifier for the user whose activity to retrieve
            limit: Maximum number of activity records to return (default: 50)
            
        Returns:
            List of activity records containing:
            - action: Type of activity performed
            - timestamp: When the activity occurred
            - details: Human-readable description of the activity
            - metadata: Additional context information
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Fetch activity from dedicated collection
            filters = [FieldFilter("user_id", "==", user_id)]
            activity_records = await self.user_activity_service.query(
                filters, 
                limit=limit, 
                order_by="timestamp", 
                order_direction="desc"
            )
            
            # If no activity records found, return basic activity from profile data
            if not activity_records:
                activity = []
                
                if user.get("last_login"):
                    activity.append({
                        "action": "login",
                        "timestamp": user["last_login"],
                        "details": "User logged in"
                    })
                
                if user.get("updated_at"):
                    activity.append({
                        "action": "profile_update",
                        "timestamp": user["updated_at"],
                        "details": "Profile updated"
                    })
                
                if user.get("created_at"):
                    activity.append({
                        "action": "account_created",
                        "timestamp": user["created_at"],
                        "details": "Account created"
                    })
                
                # Sort by timestamp (newest first) and limit
                activity.sort(key=lambda x: x["timestamp"], reverse=True)
                return activity[:limit]
            
            return activity_records
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting user activity for {user_id}: {e}")
            raise

    @monitor_performance("validate_user_permissions")
    async def validate_user_permissions(self, user_id: str, required_role: str) -> bool:
        """
        Validate user permissions using hierarchical role-based access control.
        
        Implements a hierarchical permission system where admin > scout > athlete.
        Validates that a user has sufficient role privileges to perform an action
        based on their current role level.
        
        Args:
            user_id: Unique identifier for the user to validate
            required_role: Minimum role level required for the action
            
        Returns:
            True if user has sufficient permissions
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            AuthorizationError: If user lacks required role permissions
            Exception: For other unexpected errors
        """
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            user_role = user.get("role", "athlete")
            
            # Role hierarchy: admin > scout > athlete
            role_hierarchy = {
                "admin": 3,
                "scout": 2,
                "athlete": 1
            }
            
            user_level = role_hierarchy.get(user_role, 0)
            required_level = role_hierarchy.get(required_role, 0)
            
            if user_level < required_level:
                raise AuthorizationError(f"Insufficient permissions. Required: {required_role}, Current: {user_role}")
            
            return True
            
        except (UserNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error validating permissions for {user_id}: {e}")
            raise

    @monitor_performance("update_last_login")
    async def update_last_login(self, user_id: str) -> bool:
        """
        Update user's last login timestamp with comprehensive logging.
        
        Records the timestamp of a user's most recent login activity, updates
        the profile, logs the activity for audit purposes, and invalidates
        cache to ensure data consistency.
        
        Args:
            user_id: Unique identifier for the user whose login to record
            
        Returns:
            True if last login update was successful
            
        Raises:
            UserNotFoundError: If user doesn't exist in the system
            Exception: For other unexpected errors
        """
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Update last login
            await self.user_profile_service.update(user_id, {
                "last_login": datetime.utcnow()
            })
            
            # Log activity
            await self._log_user_activity(user_id, "login", "User logged in")
            
            # Invalidate cache
            await self._invalidate_user_cache(user_id)
            
            return True
            
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error updating last login for {user_id}: {e}")
            raise

    async def _log_user_activity(self, user_id: str, action: str, details: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Log user activity to the dedicated activity collection.
        
        Records user actions for audit and analytics purposes. This method is
        designed to be non-blocking - if logging fails, it won't interrupt
        the main functionality. Creates comprehensive activity records with
        timestamps and optional metadata.
        
        Args:
            user_id: Unique identifier for the user performing the action
            action: Type of action being logged (e.g., 'login', 'profile_update')
            details: Human-readable description of the action
            metadata: Optional dictionary containing additional context information
            
        Returns:
            None
            
        Raises:
            None - Exceptions are logged but not raised to prevent breaking main functionality
        """
        try:
            activity_data = {
                "user_id": user_id,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            await self.user_activity_service.create(activity_data)
            
        except Exception as e:
            logger.error(f"Error logging user activity for {user_id}: {e}")
            # Don't raise the exception as activity logging shouldn't break main functionality

    # Helper methods for blocking and reporting
    async def _get_block_record(self, user_id: str, blocked_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get block record between two users.
        
        Queries the user_blocks collection to find existing block relationships
        between specified users. Used to check if a block already exists before
        creating new ones or to retrieve block details for removal.
        
        Args:
            user_id: ID of the user who may have blocked someone
            blocked_user_id: ID of the user who may be blocked
            
        Returns:
            Block record dictionary if exists, None otherwise
            
        Raises:
            Exception: If database query fails
        """
        try:
            filters = [
                FieldFilter("user_id", "==", user_id),
                FieldFilter("blocked_user_id", "==", blocked_user_id)
            ]
            records = await self.user_blocks_service.query(filters, limit=1)
            return records[0] if records else None
        except Exception as e:
            logger.error(f"Error getting block record: {e}")
            raise

    async def _create_block_record(self, block_data: Dict[str, Any]) -> str:
        """
        Create a new block record in the user_blocks collection.
        
        Creates a new block relationship between users, storing the block
        details including reason and timestamp. This method is used internally
        by the public block_user method.
        
        Args:
            block_data: Dictionary containing block information including:
                       user_id, blocked_user_id, reason, created_at
            
        Returns:
            Unique identifier for the created block record
            
        Raises:
            Exception: If block record creation fails
        """
        try:
            block_id = await self.user_blocks_service.create(block_data)
            return block_id
        except Exception as e:
            logger.error(f"Error creating block record: {e}")
            raise

    async def _remove_block_record(self, block_id: str) -> bool:
        """
        Remove a block record from the user_blocks collection.
        
        Deletes an existing block relationship between users, allowing them
        to interact again. This method is used internally by the unblock_user
        method to clean up block records.
        
        Args:
            block_id: Unique identifier for the block record to remove
            
        Returns:
            True if block record was successfully removed
            
        Raises:
            Exception: If block record removal fails
        """
        try:
            await self.user_blocks_service.delete(block_id)
            return True
        except Exception as e:
            logger.error(f"Error removing block record: {e}")
            raise

    async def _get_user_block_records(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all block records for a specific user.
        
        Retrieves all block relationships where the specified user is the
        blocking party. Results are ordered by creation date (newest first)
        to provide chronological context for block management.
        
        Args:
            user_id: ID of the user whose block records to retrieve
            
        Returns:
            List of block record dictionaries ordered by creation date
            
        Raises:
            Exception: If database query fails
        """
        try:
            filters = [FieldFilter("user_id", "==", user_id)]
            records = await self.user_blocks_service.query(
                filters, 
                order_by="created_at", 
                order_direction="desc"
            )
            return records
        except Exception as e:
            logger.error(f"Error getting user block records: {e}")
            raise

    async def _get_recent_report(self, reporter_id: str, reported_user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get recent report between users within a 24-hour window.
        
        Checks for existing reports between the same users within the last
        24 hours to prevent duplicate reporting. This helps maintain report
        quality and prevents spam reporting.
        
        Args:
            reporter_id: ID of the user making the report
            reported_user_id: ID of the user being reported
            
        Returns:
            Recent report record if exists within 24 hours, None otherwise
            
        Raises:
            Exception: If database query fails
        """
        try:
            # Calculate 24 hours ago
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            
            filters = [
                FieldFilter("reporter_id", "==", reporter_id),
                FieldFilter("reported_user_id", "==", reported_user_id),
                FieldFilter("created_at", ">=", twenty_four_hours_ago)
            ]
            records = await self.user_reports_service.query(filters, limit=1)
            return records[0] if records else None
        except Exception as e:
            logger.error(f"Error getting recent report: {e}")
            raise

    async def _create_report_record(self, report_data: Dict[str, Any]) -> str:
        """
        Create a new user report record in the user_reports collection.
        
        Creates a new report entry with comprehensive details including
        reason, description, evidence URL, and status. This method is used
        internally by the report_user method to persist report data.
        
        Args:
            report_data: Dictionary containing report information including:
                       reporter_id, reported_user_id, reason, description,
                       evidence_url, status, created_at
            
        Returns:
            Unique identifier for the created report record
            
        Raises:
            Exception: If report record creation fails
        """
        try:
            report_id = await self.user_reports_service.create(report_data)
            return report_id
        except Exception as e:
            logger.error(f"Error creating report record: {e}")
            raise 