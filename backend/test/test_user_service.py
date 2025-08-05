import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.user_service import UserService
from app.models.user import UserSettings, UserUpdate
from app.api.exceptions import UserNotFoundError, InvalidUserDataError, UserAlreadyExistsError, AuthorizationError


class TestUserService:
    """Test cases for the enhanced UserService"""
    
    @pytest.fixture
    def user_service(self):
        """Create a UserService instance with mocked database services"""
        # Create service without calling __init__ to avoid Firebase initialization
        service = UserService.__new__(UserService)
        
        # Mock all database services
        service.user_service = Mock()
        service.user_profile_service = Mock()
        service.user_blocks_service = Mock()
        service.user_reports_service = Mock()
        service.user_activity_service = Mock()
        
        # Initialize cache and locks
        service._cache = {}
        service._cache_lock = asyncio.Lock()
        service._cache_ttl = timedelta(minutes=15)  # Add missing cache TTL
        
        return service
    
    @pytest.fixture
    def mock_user_data(self):
        """Sample user data for testing"""
        return {
            "id": "user123",
            "email": "test@example.com",
            "role": "athlete",
            "status": "active",
            "created_at": datetime.now(),
            "username": "testuser",
            "phone_number": "+1234567890",
            "is_verified": False,
            "is_active": True,
            "profile_completion": 50,
            "settings": {
                "notifications_enabled": True,
                "privacy_level": "public"
            }
        }
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_with_cache(self, user_service, mock_user_data):
        """Test getting user by ID with caching"""
        # Mock database response
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # First call - should fetch from database
        result = await user_service.get_user_by_id("user123")
        
        assert result["id"] == "user123"
        assert result["email"] == "test@example.com"
        
        # Second call - should use cache
        result2 = await user_service.get_user_by_id("user123")
        
        assert result2 == result
        # Verify database was only called once
        user_service.user_service.get_by_id.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service):
        """Test getting non-existent user by ID"""
        user_service.user_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(UserNotFoundError):
            await user_service.get_user_by_id("nonexistent")
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_validation(self, user_service):
        """Test email validation in get_user_by_email"""
        with pytest.raises(InvalidUserDataError, match="Email is required"):
            await user_service.get_user_by_email("")
        
        with pytest.raises(InvalidUserDataError, match="Email is required"):
            await user_service.get_user_by_email("   ")
    
    @pytest.mark.asyncio
    async def test_update_user_profile_validation(self, user_service, mock_user_data):
        """Test profile update validation"""
        # Mock existing user
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_profile_service.update = AsyncMock()
        
        # Test invalid username
        profile_data = UserUpdate(username="ab")  # Too short
        with pytest.raises(InvalidUserDataError, match="Username must be at least 3 characters"):
            await user_service.update_user_profile("user123", profile_data)
    
    @pytest.mark.asyncio
    async def test_update_user_status_validation(self, user_service, mock_user_data):
        """Test user status update validation"""
        # Mock existing user
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_service.update = AsyncMock()
        
        # Test invalid status
        with pytest.raises(InvalidUserDataError, match="Invalid status"):
            await user_service.update_user_status("user123", "invalid_status")
    
    @pytest.mark.asyncio
    async def test_search_users_optimized_validation(self, user_service):
        """Test search validation"""
        with pytest.raises(InvalidUserDataError, match="Search query is required"):
            await user_service.search_users_optimized("")
        
        with pytest.raises(InvalidUserDataError, match="Search query is required"):
            await user_service.search_users_optimized("   ")
    
    @pytest.mark.asyncio
    async def test_bulk_update_user_status(self, user_service):
        """Test bulk user status update"""
        user_service.user_service.batch_update = AsyncMock(return_value=True)
        
        # Mock user existence check
        with patch.object(user_service, 'get_user_by_id', return_value={"id": "user123"}):
            result = await user_service.bulk_update_user_status(
                ["user123", "user456"], "suspended", "Test reason"
            )
        
        assert result is True
        user_service.user_service.batch_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_statistics(self, user_service):
        """Test user statistics retrieval"""
        # Mock count responses
        user_service.user_service.count = AsyncMock(side_effect=[100, 50, 5, 80, 10, 5, 30])
        user_service.user_profile_service.count = AsyncMock(return_value=40)
        
        stats = await user_service.get_user_statistics()
        
        assert stats["total_users"] == 155
        assert stats["by_role"]["athletes"] == 100
        assert stats["by_role"]["scouts"] == 50
        assert stats["by_role"]["admins"] == 5
        assert stats["by_status"]["active"] == 80
        assert stats["verification"]["verified"] == 40
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, user_service):
        """Test cache cleanup functionality"""
        # Add some expired cache entries
        expired_time = datetime.now() - timedelta(minutes=20)  # Expired
        current_time = datetime.now()
        
        user_service._cache = {
            "user1": ({"id": "user1"}, expired_time),
            "user2": ({"id": "user2"}, current_time),  # Not expired
            "user3": ({"id": "user3"}, expired_time)
        }
        
        expired_count = await user_service.cleanup_expired_cache()
        
        assert expired_count == 2
        assert "user2" in user_service._cache
        assert "user1" not in user_service._cache
        assert "user3" not in user_service._cache
    
    @pytest.mark.asyncio
    async def test_get_user_analytics(self, user_service, mock_user_data):
        """Test user analytics retrieval"""
        # Mock user and profile data
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=mock_user_data)
        
        analytics = await user_service.get_user_analytics("user123")
        
        assert analytics["profile_completion"] == 50
        assert analytics["is_verified"] is False
        assert analytics["status"] == "active"
        assert analytics["role"] == "athlete"
        assert "account_age_days" in analytics
    
    @pytest.mark.asyncio
    async def test_update_profile_completion_validation(self, user_service):
        """Test profile completion validation"""
        with pytest.raises(InvalidUserDataError, match="Profile completion must be between 0 and 100"):
            await user_service.update_profile_completion("user123", 150)
        
        with pytest.raises(InvalidUserDataError, match="Profile completion must be between 0 and 100"):
            await user_service.update_profile_completion("user123", -10)

    # New tests for blocking and reporting functionality
    @pytest.mark.asyncio
    async def test_block_user_success(self, user_service, mock_user_data):
        """Test successful user blocking"""
        # Mock existing users
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # Mock block record creation
        with patch.object(user_service, '_get_block_record', return_value=None), \
             patch.object(user_service, '_create_block_record', return_value="block123"):
            
            result = await user_service.block_user("user123", "user456", "spam")
            
            assert result["message"] == "User blocked successfully"
            assert result["id"] == "block123"
            assert result["blocked_user"]["id"] == "user456"

    @pytest.mark.asyncio
    async def test_block_user_self_blocking(self, user_service, mock_user_data):
        """Test preventing self-blocking"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        with pytest.raises(InvalidUserDataError, match="Cannot block yourself"):
            await user_service.block_user("user123", "user123")

    @pytest.mark.asyncio
    async def test_block_user_already_blocked(self, user_service, mock_user_data):
        """Test blocking already blocked user"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        with patch.object(user_service, '_get_block_record', return_value={"id": "existing_block"}):
            with pytest.raises(InvalidUserDataError, match="User is already blocked"):
                await user_service.block_user("user123", "user456")

    @pytest.mark.asyncio
    async def test_unblock_user_success(self, user_service, mock_user_data):
        """Test successful user unblocking"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        with patch.object(user_service, '_get_block_record', return_value={"id": "block123"}), \
             patch.object(user_service, '_remove_block_record', return_value=True):
            
            result = await user_service.unblock_user("user123", "user456")
            
            assert result["message"] == "User unblocked successfully"

    @pytest.mark.asyncio
    async def test_unblock_user_not_blocked(self, user_service, mock_user_data):
        """Test unblocking user that is not blocked"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        with patch.object(user_service, '_get_block_record', return_value=None):
            with pytest.raises(InvalidUserDataError, match="User is not blocked"):
                await user_service.unblock_user("user123", "user456")

    @pytest.mark.asyncio
    async def test_get_blocked_users(self, user_service, mock_user_data):
        """Test getting list of blocked users"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # Create mock blocked users
        blocked_user1 = {"id": "user456", "username": "user456", "email": "user456@example.com"}
        blocked_user2 = {"id": "user789", "username": "user789", "email": "user789@example.com"}
        
        block_records = [
            {"blocked_user_id": "user456", "created_at": datetime.now(), "reason": "spam"},
            {"blocked_user_id": "user789", "created_at": datetime.now(), "reason": "harassment"}
        ]
        
        # Mock get_user_by_id to return different users based on the ID
        async def mock_get_user_by_id(user_id):
            if user_id == "user123":
                return mock_user_data
            elif user_id == "user456":
                return blocked_user1
            elif user_id == "user789":
                return blocked_user2
            return None
        
        user_service.get_user_by_id = mock_get_user_by_id
        
        with patch.object(user_service, '_get_user_block_records', return_value=block_records):
            result = await user_service.get_blocked_users("user123")
            
            assert len(result) == 2
            assert result[0]["id"] == "user456"
            assert result[1]["id"] == "user789"

    @pytest.mark.asyncio
    async def test_report_user_success(self, user_service, mock_user_data):
        """Test successful user reporting"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        report_data = {
            "reason": "harassment",
            "description": "Inappropriate messages",
            "evidence_url": "https://example.com/evidence.jpg"
        }
        
        with patch.object(user_service, '_get_recent_report', return_value=None), \
             patch.object(user_service, '_create_report_record', return_value="report123"):
            
            result = await user_service.report_user("user123", "user456", report_data)
            
            assert result["message"] == "User reported successfully"
            assert result["id"] == "report123"
            assert result["status"] == "pending"

    @pytest.mark.asyncio
    async def test_report_user_self_reporting(self, user_service, mock_user_data):
        """Test preventing self-reporting"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        report_data = {"reason": "harassment"}
        
        with pytest.raises(InvalidUserDataError, match="Cannot report yourself"):
            await user_service.report_user("user123", "user123", report_data)

    @pytest.mark.asyncio
    async def test_report_user_missing_reason(self, user_service, mock_user_data):
        """Test reporting with missing required fields"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        report_data = {"description": "Some description"}  # Missing reason
        
        with pytest.raises(InvalidUserDataError, match="Report reason is required"):
            await user_service.report_user("user123", "user456", report_data)

    @pytest.mark.asyncio
    async def test_report_user_duplicate_report(self, user_service, mock_user_data):
        """Test preventing duplicate reports"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        report_data = {"reason": "harassment"}
        
        with patch.object(user_service, '_get_recent_report', return_value={"id": "existing_report"}):
            with pytest.raises(InvalidUserDataError, match="You have already reported this user recently"):
                await user_service.report_user("user123", "user456", report_data)

    @pytest.mark.asyncio
    async def test_get_user_activity(self, user_service, mock_user_data):
        """Test getting user activity"""
        # Mock user with activity data
        user_with_activity = {
            **mock_user_data,
            "last_login": datetime.now(),
            "updated_at": datetime.now(),
            "created_at": datetime.now() - timedelta(days=30)
        }
        
        user_service.user_service.get_by_id = AsyncMock(return_value=user_with_activity)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_activity_service.query = AsyncMock(return_value=[])
        
        activity = await user_service.get_user_activity("user123")
        
        assert len(activity) == 3
        
        # Check that all expected activities are present (order doesn't matter)
        activity_actions = [item["action"] for item in activity]
        assert "login" in activity_actions
        assert "profile_update" in activity_actions
        assert "account_created" in activity_actions

    @pytest.mark.asyncio
    async def test_validate_user_permissions_success(self, user_service, mock_user_data):
        """Test successful permission validation"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # Test athlete accessing athlete-level permissions
        result = await user_service.validate_user_permissions("user123", "athlete")
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_user_permissions_insufficient(self, user_service, mock_user_data):
        """Test insufficient permission validation"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # Test athlete trying to access admin-level permissions
        with pytest.raises(AuthorizationError, match="Insufficient permissions"):
            await user_service.validate_user_permissions("user123", "admin")

    @pytest.mark.asyncio
    async def test_update_last_login(self, user_service, mock_user_data):
        """Test updating user's last login timestamp"""
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_profile_service.update = AsyncMock()
        
        result = await user_service.update_last_login("user123")
        
        assert result is True
        user_service.user_profile_service.update.assert_called_once() 

    @pytest.mark.asyncio
    async def test_cache_size_management(self, user_service, mock_user_data):
        """Test cache size management when limit is reached"""
        # Mock database response
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        
        # Fill cache to maximum size
        for i in range(1000):
            user_id = f"user{i}"
            await user_service._set_cached_user(user_id, mock_user_data)
        
        # Verify cache size is at maximum
        assert len(user_service._cache) == 1000
        
        # Add one more user - should trigger cleanup
        await user_service._set_cached_user("user1001", mock_user_data)
        
        # Verify cache size is reduced (should be around 800 after removing 200 oldest entries)
        assert len(user_service._cache) < 1000
        assert "user1001" in user_service._cache  # New user should be in cache

    @pytest.mark.asyncio
    async def test_activity_logging(self, user_service):
        """Test activity logging functionality"""
        user_service.user_activity_service.create = AsyncMock(return_value="activity123")
        
        # Test logging activity
        await user_service._log_user_activity(
            "user123", 
            "test_action", 
            "Test activity details",
            {"test_key": "test_value"}
        )
        
        # Verify activity was logged
        user_service.user_activity_service.create.assert_called_once()
        call_args = user_service.user_activity_service.create.call_args[0][0]
        assert call_args["user_id"] == "user123"
        assert call_args["action"] == "test_action"
        assert call_args["details"] == "Test activity details"
        assert call_args["metadata"]["test_key"] == "test_value"

    @pytest.mark.asyncio
    async def test_block_user_with_activity_logging(self, user_service, mock_user_data):
        """Test blocking user with activity logging"""
        # Mock all required services
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_blocks_service.query = AsyncMock(return_value=[])  # No existing block
        user_service.user_blocks_service.create = AsyncMock(return_value="block123")
        user_service.user_activity_service.create = AsyncMock(return_value="activity123")
        
        result = await user_service.block_user("user123", "user456", "Test reason")
        
        # Verify block was created
        assert result["id"] == "block123"
        assert result["message"] == "User blocked successfully"
        
        # Verify activity was logged
        user_service.user_activity_service.create.assert_called_once()
        call_args = user_service.user_activity_service.create.call_args[0][0]
        assert call_args["action"] == "block_user"
        assert "Blocked user" in call_args["details"]

    @pytest.mark.asyncio
    async def test_report_user_with_activity_logging(self, user_service, mock_user_data):
        """Test reporting user with activity logging"""
        # Mock all required services
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_reports_service.query = AsyncMock(return_value=[])  # No recent reports
        user_service.user_reports_service.create = AsyncMock(return_value="report123")
        user_service.user_activity_service.create = AsyncMock(return_value="activity123")
        
        report_data = {"reason": "harassment", "description": "Test report"}
        result = await user_service.report_user("user123", "user456", report_data)
        
        # Verify report was created
        assert result["id"] == "report123"
        assert result["message"] == "User reported successfully"
        
        # Verify activity was logged
        user_service.user_activity_service.create.assert_called_once()
        call_args = user_service.user_activity_service.create.call_args[0][0]
        assert call_args["action"] == "report_user"
        assert "Reported user" in call_args["details"]
        assert call_args["metadata"]["reason"] == "harassment"

    @pytest.mark.asyncio
    async def test_get_user_activity_from_collection(self, user_service, mock_user_data):
        """Test getting user activity from dedicated collection"""
        # Mock activity records from collection
        activity_records = [
            {
                "id": "activity1",
                "user_id": "user123",
                "action": "login",
                "details": "User logged in",
                "timestamp": datetime.now(),
                "metadata": {}
            },
            {
                "id": "activity2", 
                "user_id": "user123",
                "action": "block_user",
                "details": "Blocked user user456",
                "timestamp": datetime.now() - timedelta(hours=1),
                "metadata": {"blocked_user_id": "user456"}
            }
        ]
        
        user_service.user_service.get_by_id = AsyncMock(return_value=mock_user_data)
        user_service.user_profile_service.get_by_field = AsyncMock(return_value=None)
        user_service.user_activity_service.query = AsyncMock(return_value=activity_records)
        
        activity = await user_service.get_user_activity("user123")
        
        # Should return activity from collection, not profile data
        assert len(activity) == 2
        assert activity[0]["action"] == "login"
        assert activity[1]["action"] == "block_user"
        
        # Verify query was called with correct filters
        user_service.user_activity_service.query.assert_called_once() 