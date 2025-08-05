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
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)

# Cache configuration
MAX_CACHE_SIZE = 1000
CACHE_TTL_MINUTES = 15


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
    
    async def _get_cached_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from cache if available and not expired"""
        if user_id in self._cache:
            cached_data, timestamp = self._cache[user_id]
            if datetime.now() - timestamp < self._cache_ttl:
                return cached_data
            else:
                # Remove expired cache entry
                del self._cache[user_id]
        return None
    
    async def _set_cached_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """Cache user data with timestamp and size management"""
        async with self._cache_lock:
            # Check cache size and remove oldest entries if needed
            if len(self._cache) >= MAX_CACHE_SIZE:
                # Remove oldest entries (20% of cache size)
                remove_count = MAX_CACHE_SIZE // 5
                oldest_entries = sorted(
                    self._cache.items(), 
                    key=lambda x: x[1][1]
                )[:remove_count]
                
                for key, _ in oldest_entries:
                    del self._cache[key]
                
                logger.info(f"Cache size limit reached. Removed {remove_count} oldest entries.")
            
            self._cache[user_id] = (user_data, datetime.now())
    
    async def _invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate user cache"""
        async with self._cache_lock:
            if user_id in self._cache:
                del self._cache[user_id]
    
    async def _fetch_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user data from database"""
        try:
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
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID with caching"""
        try:
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
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email with validation"""
        try:
            if not email or not email.strip():
                raise InvalidUserDataError("Email is required")
            
            user_doc = await self.user_service.get_by_field("email", email.strip().lower())
            if not user_doc:
                return None
            
            # Get user profile
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_doc["id"])
            
            # Combine user and profile data
            result = {**user_doc}
            if profile_doc:
                result.update(profile_doc)
            
            return result
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            raise
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username with validation"""
        try:
            if not username or not username.strip():
                raise InvalidUserDataError("Username is required")
            
            profile_doc = await self.user_profile_service.get_by_field("username", username.strip())
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
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            raise
    
    async def update_user_profile(self, user_id: str, profile_data: UserUpdate) -> Dict[str, Any]:
        """Update user profile with validation"""
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate input data
            if profile_data.username is not None:
                if len(profile_data.username.strip()) < 3:
                    raise InvalidUserDataError("Username must be at least 3 characters long")
                
                # Check if username is already taken by another user
                existing_user = await self.get_user_by_username(profile_data.username.strip())
                if existing_user and existing_user["id"] != user_id:
                    raise UserAlreadyExistsError(f"Username {profile_data.username} is already taken")
            
            # Prepare update data
            update_data = {}
            if profile_data.username is not None:
                update_data["username"] = profile_data.username.strip()
            if profile_data.phone_number is not None:
                update_data["phone_number"] = profile_data.phone_number.strip() if profile_data.phone_number else None
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
    
    async def update_user_settings(self, user_id: str, settings: UserSettings) -> Dict[str, Any]:
        """Update user settings with validation"""
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate settings
            if not isinstance(settings, UserSettings):
                raise InvalidUserDataError("Invalid settings format")
            
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
    
    async def get_user_settings(self, user_id: str) -> UserSettings:
        """Get user settings with default fallback"""
        try:
            profile_doc = await self.user_profile_service.get_by_field("user_id", user_id)
            if not profile_doc or "settings" not in profile_doc:
                return UserSettings()
            
            return UserSettings(**profile_doc["settings"])
            
        except Exception as e:
            logger.error(f"Error getting user settings {user_id}: {e}")
            raise
    
    async def update_profile_completion(self, user_id: str, completion_percentage: int) -> bool:
        """Update user profile completion percentage with validation"""
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
    
    async def get_users_by_role(self, role: str, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        """Get users by role with pagination and validation"""
        try:
            # Validate role
            valid_roles = ["athlete", "scout", "admin"]
            if role not in valid_roles:
                raise InvalidUserDataError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
            
            # Validate pagination parameters
            if limit < 1 or limit > 1000:
                raise InvalidUserDataError("Limit must be between 1 and 1000")
            if offset < 0:
                raise InvalidUserDataError("Offset must be non-negative")
            
            filters = [FieldFilter("role", "==", role)]
            
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
    
    async def get_users_by_status(self, status: str, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        """Get users by status with pagination and validation"""
        try:
            # Validate status
            valid_statuses = ["active", "suspended", "deleted"]
            if status not in valid_statuses:
                raise InvalidUserDataError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
            # Validate pagination parameters
            if limit < 1 or limit > 1000:
                raise InvalidUserDataError("Limit must be between 1 and 1000")
            if offset < 0:
                raise InvalidUserDataError("Offset must be non-negative")
            
            filters = [FieldFilter("status", "==", status)]
            
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
    
    async def update_user_status(self, user_id: str, status: str, reason: Optional[str] = None) -> bool:
        """Update user status with validation"""
        try:
            # Validate user exists
            user = await self.get_user_by_id(user_id)
            if not user:
                raise UserNotFoundError(user_id)
            
            # Validate status
            valid_statuses = ["active", "suspended", "deleted"]
            if status not in valid_statuses:
                raise InvalidUserDataError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
            update_data = {"status": status}
            if reason:
                update_data["status_reason"] = reason
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
    
    async def search_users_optimized(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Optimized user search with proper indexing and deduplication"""
        try:
            if not query or not query.strip():
                raise InvalidUserDataError("Search query is required")
            
            query = query.strip()
            
            # Use Firestore's built-in search with proper indexing
            # Search by email prefix
            email_filters = [
                FieldFilter("email", ">=", query),
                FieldFilter("email", "<=", query + "\uf8ff")
            ]
            
            email_users = await self.user_service.query(email_filters, limit)
            
            # Search by username prefix
            username_filters = [
                FieldFilter("username", ">=", query),
                FieldFilter("username", "<=", query + "\uf8ff")
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
        """Merge search results efficiently"""
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
    
    async def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """Enhanced user analytics with comprehensive data"""
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
    
    async def delete_user_account(self, user_id: str) -> bool:
        """Soft delete user account with validation"""
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
    
    async def verify_user(self, user_id: str) -> bool:
        """Verify user account with validation"""
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
    
    async def bulk_update_user_status(self, user_ids: List[str], status: str, reason: Optional[str] = None) -> bool:
        """Bulk update user status for admin operations"""
        try:
            # Validate status
            valid_statuses = ["active", "suspended", "deleted"]
            if status not in valid_statuses:
                raise InvalidUserDataError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
            # Validate user IDs
            if not user_ids:
                raise InvalidUserDataError("User IDs list cannot be empty")
            
            # Prepare updates
            updates = []
            for user_id in user_ids:
                update_data = {"status": status}
                if reason:
                    update_data["status_reason"] = reason
                    update_data["status_updated_at"] = datetime.utcnow()
                updates.append((user_id, update_data))
            
            # Perform bulk update
            success = await self.user_service.batch_update(updates)
            
            # Invalidate cache for all updated users
            for user_id in user_ids:
                await self._invalidate_user_cache(user_id)
            
            return success
            
        except InvalidUserDataError:
            raise
        except Exception as e:
            logger.error(f"Error bulk updating user status: {e}")
            raise
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get platform user statistics for admin dashboard"""
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
        """Clean up expired cache entries"""
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

    # User blocking and reporting functionality
    async def block_user(self, user_id: str, blocked_user_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Block a user"""
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
            
            # Create block record
            block_data = {
                "user_id": user_id,
                "blocked_user_id": blocked_user_id,
                "reason": reason,
                "created_at": datetime.utcnow()
            }
            
            block_id = await self._create_block_record(block_data)
            
            # Log activity
            await self._log_user_activity(
                user_id, 
                "block_user", 
                f"Blocked user {blocked_user.get('username', blocked_user_id)}",
                {"blocked_user_id": blocked_user_id, "reason": reason}
            )
            
            return {
                "id": block_id,
                "message": "User blocked successfully",
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

    async def unblock_user(self, user_id: str, blocked_user_id: str) -> Dict[str, Any]:
        """Unblock a user"""
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

    async def get_blocked_users(self, user_id: str) -> List[Dict[str, Any]]:
        """Get list of users blocked by the specified user"""
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

    async def report_user(self, reporter_id: str, reported_user_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Report a user"""
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
            
            # Validate report data
            required_fields = ["reason"]
            for field in required_fields:
                if field not in report_data or not report_data[field]:
                    raise InvalidUserDataError(f"Report {field} is required")
            
            # Check for duplicate reports (within 24 hours)
            recent_report = await self._get_recent_report(reporter_id, reported_user_id)
            if recent_report:
                raise InvalidUserDataError("You have already reported this user recently")
            
            # Create report record
            report_record = {
                "reporter_id": reporter_id,
                "reported_user_id": reported_user_id,
                "reason": report_data["reason"],
                "description": report_data.get("description"),
                "evidence_url": report_data.get("evidence_url"),
                "status": "pending",
                "created_at": datetime.utcnow()
            }
            
            report_id = await self._create_report_record(report_record)
            
            # Log activity
            await self._log_user_activity(
                reporter_id, 
                "report_user", 
                f"Reported user {reported_user.get('username', reported_user_id)} for {report_data['reason']}",
                {
                    "reported_user_id": reported_user_id,
                    "reason": report_data["reason"],
                    "report_id": report_id
                }
            )
            
            return {
                "id": report_id,
                "message": "User reported successfully",
                "status": "pending"
            }
            
        except (UserNotFoundError, InvalidUserDataError):
            raise
        except Exception as e:
            logger.error(f"Error reporting user {reported_user_id} by {reporter_id}: {e}")
            raise

    async def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user activity log from dedicated collection"""
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

    async def validate_user_permissions(self, user_id: str, required_role: str) -> bool:
        """Validate if user has required role permissions"""
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

    async def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp"""
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
        """Log user activity to the activity collection"""
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
        """Get block record between two users"""
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
        """Create a new block record"""
        try:
            block_id = await self.user_blocks_service.create(block_data)
            return block_id
        except Exception as e:
            logger.error(f"Error creating block record: {e}")
            raise

    async def _remove_block_record(self, block_id: str) -> bool:
        """Remove a block record"""
        try:
            await self.user_blocks_service.delete(block_id)
            return True
        except Exception as e:
            logger.error(f"Error removing block record: {e}")
            raise

    async def _get_user_block_records(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all block records for a user"""
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
        """Get recent report between users (within 24 hours)"""
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
        """Create a new report record"""
        try:
            report_id = await self.user_reports_service.create(report_data)
            return report_id
        except Exception as e:
            logger.error(f"Error creating report record: {e}")
            raise 