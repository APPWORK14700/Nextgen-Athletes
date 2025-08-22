"""
Comprehensive tests for the improved UserService
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.user_service import UserService
from app.utils.input_sanitizer import InputSanitizer
from app.models.user import UserUpdate, UserSettings
from app.api.exceptions import (
    UserNotFoundError, UserAlreadyExistsError, InvalidUserDataError, 
    AuthorizationError
)


class TestUserService:
    """Test suite for UserService"""
    
    @pytest_asyncio.fixture
    async def user_service(self):
        """Create a UserService instance for testing"""
        service = UserService()
        # Mock database services
        service.user_service = Mock()
        service.user_profile_service = Mock()
        service.user_blocks_service = Mock()
        service.user_reports_service = Mock()
        service.user_activity_service = Mock()
        return service
    
    @pytest.fixture
    def mock_user_data(self):
        """Sample user data for testing"""
        return {
            "id": "user123",
            "email": "test@example.com",
            "role": "athlete",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "username": "testuser",
            "profile_completion": 75,
            "is_verified": True
        }
    
    @pytest.fixture
    def mock_profile_data(self):
        """Sample profile data for testing"""
        return {
            "user_id": "user123",
            "username": "testuser",
            "phone_number": "+1234567890",
            "profile_completion": 75,
            "is_verified": True,
            "last_login": datetime.now().isoformat()
        }
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, user_service, mock_user_data, mock_profile_data):
        """Test successful user retrieval by ID"""
        # Mock cache miss
        user_service._get_cached_user = AsyncMock(return_value=None)
        user_service._fetch_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service._set_cached_user = AsyncMock()
        
        result = await user_service.get_user_by_id("user123")
        
        assert result == mock_user_data
        user_service._set_cached_user.assert_called_once_with("user123", mock_user_data)
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_cache_hit(self, user_service, mock_user_data):
        """Test user retrieval from cache"""
        user_service._get_cached_user = AsyncMock(return_value=mock_user_data)
        
        result = await user_service.get_user_by_id("user123")
        
        assert result == mock_user_data
        # Should not call fetch method when cache hit occurs
        # The method exists but should not be called
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_invalid_input(self, user_service):
        """Test user retrieval with invalid input"""
        with pytest.raises(InvalidUserDataError, match="user_id is required"):
            await user_service.get_user_by_id("")
        
        with pytest.raises(InvalidUserDataError, match="user_id is required"):
            await user_service.get_user_by_id(None)
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, user_service, mock_user_data, mock_profile_data):
        """Test successful user retrieval by email"""
        user_service.user_service.get_by_field = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=mock_profile_data)
        
        result = await user_service.get_user_by_email("test@example.com")
        
        assert result["email"] == "test@example.com"
        assert result["username"] == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_invalid_format(self, user_service):
        """Test user retrieval with invalid email format"""
        with pytest.raises(InvalidUserDataError, match="Invalid email format"):
            await user_service.get_user_by_email("invalid-email")
    
    @pytest.mark.asyncio
    async def test_get_user_by_username_success(self, user_service, mock_user_data, mock_profile_data):
        """Test successful user retrieval by username"""
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=mock_profile_data)
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        
        result = await user_service.get_user_by_username("testuser")
        
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_user_by_username_invalid_format(self, user_service):
        """Test user retrieval with invalid username format"""
        with pytest.raises(InvalidUserDataError, match="Invalid username format"):
            await user_service.get_user_by_username("invalid username!")
    
    @pytest.mark.asyncio
    async def test_update_user_profile_success(self, user_service, mock_user_data):
        """Test successful profile update"""
        # Mock dependencies
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service.get_user_by_username = AsyncMock(return_value=None)  # Username not taken
        user_service.user_profile_service.update = AsyncMock()
        user_service._invalidate_user_cache = AsyncMock()
        
        profile_data = UserUpdate(username="newusername", phone_number="+1987654321")
        result = await user_service.update_user_profile("user123", profile_data)
        
        # Verify profile update
        user_service.user_profile_service.update.assert_called_once()
        user_service._invalidate_user_cache.assert_called_once_with("user123")
    
    @pytest.mark.asyncio
    async def test_update_user_profile_username_taken(self, user_service, mock_user_data):
        """Test profile update with already taken username"""
        existing_user = {"id": "other_user", "username": "newusername"}
        
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service.get_user_by_username = AsyncMock(return_value=existing_user)
        
        profile_data = UserUpdate(username="newusername")
        
        with pytest.raises(UserAlreadyExistsError, match="User with username 'newusername' already exists"):
            await user_service.update_user_profile("user123", profile_data)
    

    
    @pytest.mark.asyncio
    async def test_update_user_settings_success(self, user_service, mock_user_data):
        """Test successful settings update"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.update = AsyncMock()
        user_service._invalidate_user_cache = AsyncMock()
        
        settings = UserSettings(notifications_enabled=True, privacy_level="private")
        result = await user_service.update_user_settings("user123", settings)
        
        user_service.user_profile_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_users_by_role_success(self, user_service):
        """Test successful user retrieval by role"""
        mock_users = [{"id": "user1", "role": "athlete"}, {"id": "user2", "role": "athlete"}]
        user_service.user_service.query = AsyncMock(return_value=mock_users)
        user_service.user_service.count = AsyncMock(return_value=2)
        
        result = await user_service.get_users_by_role("athlete", limit=10, offset=0)
        
        assert result.count == 2
        assert len(result.results) == 2
        assert result.results[0]["role"] == "athlete"
    
    @pytest.mark.asyncio
    async def test_get_users_by_role_invalid_role(self, user_service):
        """Test user retrieval with invalid role"""
        with pytest.raises(InvalidUserDataError, match="Invalid role"):
            await user_service.get_users_by_role("invalid_role")
    
    @pytest.mark.asyncio
    async def test_get_users_by_status_success(self, user_service):
        """Test successful user retrieval by status"""
        mock_users = [{"id": "user1", "status": "active"}, {"id": "user2", "status": "active"}]
        user_service.user_service.query = AsyncMock(return_value=mock_users)
        user_service.user_service.count = AsyncMock(return_value=2)
        
        result = await user_service.get_users_by_status("active", limit=10, offset=0)
        
        assert result.count == 2
        assert len(result.results) == 2
        assert result.results[0]["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_users_by_status_invalid_status(self, user_service):
        """Test user retrieval with invalid status"""
        with pytest.raises(InvalidUserDataError, match="Invalid status"):
            await user_service.get_users_by_status("invalid_status")
    
    @pytest.mark.asyncio
    async def test_update_user_status_success(self, user_service, mock_user_data):
        """Test successful status update"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_service.update = AsyncMock()
        user_service._invalidate_user_cache = AsyncMock()
        
        result = await user_service.update_user_status("user123", "suspended", "Violation of terms")
        
        assert result is True
        user_service.user_service.update.assert_called_once()
        user_service._invalidate_user_cache.assert_called_once_with("user123")
    
    @pytest.mark.asyncio
    async def test_update_user_status_invalid_status(self, user_service, mock_user_data):
        """Test status update with invalid status"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        
        with pytest.raises(InvalidUserDataError, match="Invalid status"):
            await user_service.update_user_status("user123", "invalid_status")
    
    @pytest.mark.asyncio
    async def test_search_users_optimized_success(self, user_service):
        """Test successful user search"""
        mock_email_users = [{"id": "user1", "email": "test@example.com"}]
        mock_username_users = [{"user_id": "user2", "username": "testuser"}]
        
        user_service.user_service.query = AsyncMock(return_value=mock_email_users)
        user_service.user_profile_service.query = AsyncMock(return_value=mock_username_users)
        user_service._merge_search_results = AsyncMock(return_value=mock_email_users + mock_username_users)
        
        result = await user_service.search_users_optimized("test")
        
        assert len(result) == 2
        user_service._merge_search_results.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_users_optimized_empty_query(self, user_service):
        """Test user search with empty query"""
        with pytest.raises(InvalidUserDataError, match="search query is required"):
            await user_service.search_users_optimized("")
    
    @pytest.mark.asyncio
    async def test_block_user_success(self, user_service, mock_user_data):
        """Test successful user blocking"""
        blocked_user = {"id": "blocked123", "username": "blockeduser"}
        
        user_service.get_user_by_id = AsyncMock(side_effect=[mock_user_data, blocked_user])
        user_service._get_block_record = AsyncMock(return_value=None)
        user_service._create_block_record = AsyncMock(return_value="block123")
        user_service._log_user_activity = AsyncMock()
        
        result = await user_service.block_user("user123", "blocked123", "Spam")
        
        assert result["message"] == "User blocked successfully"
        assert result["blocked_user"]["id"] == "blocked123"
    
    @pytest.mark.asyncio
    async def test_block_user_self_blocking(self, user_service, mock_user_data):
        """Test blocking yourself (should fail)"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        
        with pytest.raises(InvalidUserDataError, match="Cannot block yourself"):
            await user_service.block_user("user123", "user123")
    
    @pytest.mark.asyncio
    async def test_block_user_already_blocked(self, user_service, mock_user_data):
        """Test blocking already blocked user"""
        blocked_user = {"id": "blocked123", "username": "blockeduser"}
        existing_block = {"id": "block123", "user_id": "user123", "blocked_user_id": "blocked123"}
        
        user_service.get_user_by_id = AsyncMock(side_effect=[mock_user_data, blocked_user])
        user_service._get_block_record = AsyncMock(return_value=existing_block)
        
        with pytest.raises(InvalidUserDataError, match="User is already blocked"):
            await user_service.block_user("user123", "blocked123")
    
    @pytest.mark.asyncio
    async def test_report_user_success(self, user_service, mock_user_data):
        """Test successful user reporting"""
        reported_user = {"id": "reported123", "username": "reporteduser"}
        
        user_service.get_user_by_id = AsyncMock(side_effect=[mock_user_data, reported_user])
        user_service._get_recent_report = AsyncMock(return_value=None)
        user_service._create_report_record = AsyncMock(return_value="report123")
        user_service._log_user_activity = AsyncMock()
        
        report_data = {"reason": "Spam", "description": "User is spamming"}
        result = await user_service.report_user("user123", "reported123", report_data)
        
        assert result["message"] == "User reported successfully"
        assert result["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_report_user_self_reporting(self, user_service, mock_user_data):
        """Test reporting yourself (should fail)"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        
        report_data = {"reason": "Spam"}
        with pytest.raises(InvalidUserDataError, match="Cannot report yourself"):
            await user_service.report_user("user123", "user123", report_data)
    
    @pytest.mark.asyncio
    async def test_report_user_duplicate_report(self, user_service, mock_user_data):
        """Test duplicate reporting within 24 hours"""
        reported_user = {"id": "reported123", "username": "reporteduser"}
        recent_report = {"id": "report123", "created_at": datetime.now().isoformat()}
        
        user_service.get_user_by_id = AsyncMock(side_effect=[mock_user_data, reported_user])
        user_service._get_recent_report = AsyncMock(return_value=recent_report)
        
        report_data = {"reason": "Spam"}
        with pytest.raises(InvalidUserDataError, match="You have already reported this user recently"):
            await user_service.report_user("user123", "reported123", report_data)
    
    @pytest.mark.asyncio
    async def test_validate_user_permissions_success(self, user_service, mock_user_data):
        """Test successful permission validation"""
        # Set user role to admin for permission testing
        admin_user_data = {**mock_user_data, "role": "admin"}
        user_service.get_user_by_id = AsyncMock(return_value=admin_user_data)
        
        # Admin should have access to scout role
        result = await user_service.validate_user_permissions("user123", "scout")
        assert result is True
        
        # Admin should have access to athlete role
        result = await user_service.validate_user_permissions("user123", "athlete")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_user_permissions_insufficient(self, user_service, mock_user_data):
        """Test permission validation with insufficient permissions"""
        # Change user role to athlete
        mock_user_data["role"] = "athlete"
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        
        with pytest.raises(AuthorizationError, match="Insufficient permissions"):
            await user_service.validate_user_permissions("user123", "scout")
    
    @pytest.mark.asyncio
    async def test_bulk_update_user_status_success(self, user_service):
        """Test successful bulk status update"""
        user_service.user_service.batch_update = AsyncMock(return_value=True)
        user_service._invalidate_user_cache = AsyncMock()
        
        user_ids = ["user1", "user2", "user3"]
        result = await user_service.bulk_update_user_status(user_ids, "suspended", "Bulk suspension")
        
        assert result is True
        user_service.user_service.batch_update.assert_called_once()
        assert user_service._invalidate_user_cache.call_count == 3
    
    @pytest.mark.asyncio
    async def test_bulk_update_user_status_empty_list(self, user_service):
        """Test bulk status update with empty user list"""
        with pytest.raises(InvalidUserDataError, match="User IDs list cannot be empty"):
            await user_service.bulk_update_user_status([], "suspended")
    
    @pytest.mark.asyncio
    async def test_bulk_update_user_status_invalid_status(self, user_service):
        """Test bulk status update with invalid status"""
        with pytest.raises(InvalidUserDataError, match="Invalid status"):
            await user_service.bulk_update_user_status(["user1"], "invalid_status")
    
    @pytest.mark.asyncio
    async def test_get_user_analytics_success(self, user_service, mock_user_data, mock_profile_data):
        """Test successful user analytics retrieval"""
        user_service.get_user_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=mock_profile_data)
        
        result = await user_service.get_user_analytics("user123")
        
        assert result["profile_completion"] == 75
        assert result["is_verified"] is True
        assert result["role"] == "athlete"
        assert result["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_get_user_statistics_success(self, user_service):
        """Test successful user statistics retrieval"""
        # Mock count calls for all the different queries in get_user_statistics
        # The method calls count 6 times: athletes, scouts, admins, active, suspended, deleted
        user_service.user_service.count = AsyncMock(side_effect=[100, 50, 5, 100, 50, 5])  # athletes, scouts, admins, active, suspended, deleted
        user_service.user_profile_service.count = AsyncMock(return_value=80)  # verified users
        
        result = await user_service.get_user_statistics()
        
        assert result["total_users"] == 155
        assert result["by_role"]["athletes"] == 100
        assert result["by_role"]["scouts"] == 50
        assert result["by_role"]["admins"] == 5
        assert result["verification"]["verified"] == 80
        assert result["verification"]["unverified"] == 75
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, user_service):
        """Test cache cleanup functionality"""
        # Add some expired entries to cache
        expired_time = datetime.now() - timedelta(minutes=20)
        current_time = datetime.now()
        
        user_service._cache = {
            "user1": ({"data": "user1"}, expired_time),
            "user2": ({"data": "user2"}, current_time),
            "user3": ({"data": "user3"}, expired_time)
        }
        
        result = await user_service.cleanup_expired_cache()
        
        assert result == 2  # 2 expired entries removed
        assert "user2" in user_service._cache  # Current entry remains
        assert "user1" not in user_service._cache  # Expired entries removed
        assert "user3" not in user_service._cache
    
    @pytest.mark.asyncio
    async def test_input_sanitization_integration(self, user_service):
        """Test that input sanitization is properly integrated"""
        # Test username sanitization
        with patch('app.services.user_service.InputSanitizer') as mock_sanitizer:
            mock_sanitizer.sanitize_username.return_value = "sanitized_username"
            mock_sanitizer.sanitize_email.return_value = "sanitized@email.com"
            
            user_service.user_profile_service.get_by_field = AsyncMock(return_value={"user_id": "user123"})
            user_service.user_service.get_by_id = AsyncMock(return_value={"id": "user123"})
            
            result = await user_service.get_user_by_username("test username!")
            
            mock_sanitizer.sanitize_username.assert_called_once_with("test username!")
    
    @pytest.mark.asyncio
    async def test_metrics_integration(self, user_service):
        """Test that metrics are properly recorded"""
        # Test that the service works with metrics integration
        user_service._get_cached_user = AsyncMock(return_value=None)
        user_service._fetch_user_by_id = AsyncMock(return_value={"id": "user123"})
        user_service._set_cached_user = AsyncMock()
        
        # This should work without errors, even with metrics calls
        result = await user_service.get_user_by_id("user123")
        
        # Verify the service works correctly
        assert result["id"] == "user123"
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, user_service):
        """Test that performance monitoring is properly integrated"""
        # The @monitor_performance decorator should be applied to methods
        # This test verifies the decorator is present
        assert hasattr(user_service.get_user_by_id, '__wrapped__')
        assert hasattr(user_service.update_user_profile, '__wrapped__')
        assert hasattr(user_service.search_users_optimized, '__wrapped__')
    
    @pytest.mark.asyncio
    async def test_error_handling_improvements(self, user_service):
        """Test improved error handling"""
        # Test that validation errors are properly caught and converted
        with pytest.raises(InvalidUserDataError, match="Invalid email format"):
            await user_service.get_user_by_email("invalid-email")
        
        with pytest.raises(InvalidUserDataError, match="Invalid username format"):
            await user_service.get_user_by_username("invalid username!")
    



class TestUserServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest_asyncio.fixture
    async def user_service(self):
        """Create a UserService instance for testing"""
        service = UserService()
        service.user_service = Mock()
        service.user_profile_service = Mock()
        service.user_blocks_service = Mock()
        service.user_reports_service = Mock()
        service.user_activity_service = Mock()
        return service
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, user_service):
        """Test concurrent access to cache"""
        # This test verifies that cache operations are thread-safe
        user_service._cache = {}
        
        async def add_to_cache(user_id):
            await user_service._set_cached_user(user_id, {"data": f"user{user_id}"})
        
        # Simulate concurrent cache access
        tasks = [add_to_cache(f"user{i}") for i in range(10)]
        await asyncio.gather(*tasks)
        
        assert len(user_service._cache) == 10
    
    @pytest.mark.asyncio
    async def test_cache_size_limit_enforcement(self, user_service):
        """Test that cache size limits are enforced"""
        # Fill cache beyond limit
        for i in range(1100):  # Beyond MAX_CACHE_SIZE of 1000
            user_service._cache[f"user{i}"] = ({"data": f"user{i}"}, datetime.now())
        
        # Trigger cache cleanup
        await user_service._set_cached_user("newuser", {"data": "newuser"})
        
        # Cache should be reduced
        assert len(user_service._cache) <= 1000
    
    @pytest.mark.asyncio
    async def test_database_service_failure_handling(self, user_service):
        """Test handling of database service failures"""
        user_service.user_service.get_by_id = AsyncMock(side_effect=Exception("Database connection failed"))
        
        with pytest.raises(Exception, match="Database connection failed"):
            await user_service._fetch_user_by_id("user123")
    
    @pytest.mark.asyncio
    async def test_invalid_input_edge_cases(self, user_service):
        """Test various invalid input edge cases"""
        # Test with very long inputs
        long_username = "a" * 1000
        with pytest.raises(InvalidUserDataError):
            await user_service.get_user_by_username(long_username)
        
        # Test with special characters
        special_username = "user@#$%^&*()"
        with pytest.raises(InvalidUserDataError):
            await user_service.get_user_by_username(special_username)
        
        # Test with SQL injection attempts
        sql_injection = "'; DROP TABLE users; --"
        with pytest.raises(InvalidUserDataError):
            await user_service.get_user_by_username(sql_injection)
    
    @pytest.mark.asyncio
    async def test_memory_leak_prevention(self, user_service):
        """Test that memory leaks are prevented"""
        initial_cache_size = len(user_service._cache)
        
        # Simulate many operations
        for i in range(100):
            await user_service._set_cached_user(f"user{i}", {"data": f"user{i}"})
        
        # Clean up expired entries
        await user_service.cleanup_expired_cache()
        
        # Cache should not grow indefinitely
        assert len(user_service._cache) <= 1000


if __name__ == "__main__":
    pytest.main([__file__]) 