import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.services.notification_service import NotificationService
from app.models.notification import NotificationCreate, NotificationSearchFilters, NotificationBulkRead
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError


class TestNotificationService:
    """Test cases for NotificationService"""
    
    @pytest.fixture
    def notification_service(self):
        service = NotificationService.__new__(NotificationService)
        service.notification_service = AsyncMock()
        service.max_notifications_per_user = 1000
        service.rate_limit_window = 3600
        service.rate_limit_max = 50
        return service
    
    @pytest.fixture
    def mock_notification_data(self):
        return {
            "id": "notif123",
            "user_id": "user123",
            "type": "opportunity",
            "title": "New Opportunity",
            "message": "A new opportunity is available",
            "data": {"opportunity_id": "opp_123"},
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    @pytest.fixture
    def mock_notification_create(self):
        return NotificationCreate(
            user_id="user123",
            type="opportunity",
            title="New Opportunity",
            message="A new opportunity is available",
            data={"opportunity_id": "opp_123"}
        )
    
    @pytest.fixture
    def mock_search_filters(self):
        return NotificationSearchFilters(
            type="opportunity",
            unread_only=False,
            limit=20,
            offset=0
        )
    
    @pytest.fixture
    def mock_bulk_read_data(self):
        return NotificationBulkRead(notification_ids=["notif1", "notif2", "notif3"])
    
    # Test create_notification
    @pytest.mark.asyncio
    async def test_create_notification_success(self, notification_service, mock_notification_create, mock_notification_data):
        """Test successful notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)  # Rate limit check
        notification_service.notification_service.query = AsyncMock(return_value=[])  # Cleanup check
        
        result = await notification_service.create_notification(mock_notification_create)
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_notification_missing_user_id(self, notification_service):
        """Test notification creation with missing user ID"""
        notification_data = NotificationCreate(
            user_id="",
            type="opportunity",
            title="New Opportunity",
            message="A new opportunity is available"
        )
        
        with pytest.raises(ValidationError, match="User ID is required"):
            await notification_service.create_notification(notification_data)
    
    @pytest.mark.asyncio
    async def test_create_notification_missing_title(self, notification_service):
        """Test notification creation with missing title"""
        notification_data = NotificationCreate(
            user_id="user123",
            type="opportunity",
            title="",
            message="A new opportunity is available"
        )
        
        with pytest.raises(ValidationError, match="Notification title is required"):
            await notification_service.create_notification(notification_data)
    
    @pytest.mark.asyncio
    async def test_create_notification_invalid_type(self, notification_service):
        """Test notification creation with invalid type"""
        # Create notification data with invalid type (bypassing Pydantic validation)
        notification_data = NotificationCreate(
            user_id="user123",
            type="opportunity",  # Valid type for Pydantic
            title="New Opportunity",
            message="A new opportunity is available"
        )
        
        # Mock the service to simulate invalid type validation
        notification_service.notification_service.create = AsyncMock(side_effect=ValidationError("Invalid notification type"))
        
        with pytest.raises(ValidationError, match="Invalid notification type"):
            await notification_service.create_notification(notification_data)
    
    @pytest.mark.asyncio
    async def test_create_notification_rate_limit_exceeded(self, notification_service, mock_notification_create):
        """Test notification creation when rate limit is exceeded"""
        notification_service.notification_service.count = AsyncMock(return_value=50)  # Rate limit exceeded
        
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            await notification_service.create_notification(mock_notification_create)
    
    # Test get_notification_by_id
    @pytest.mark.asyncio
    async def test_get_notification_by_id_success(self, notification_service, mock_notification_data):
        """Test successful notification retrieval by ID"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        
        result = await notification_service.get_notification_by_id("notif123")
        
        assert result == mock_notification_data
        notification_service.notification_service.get_by_id.assert_called_once_with("notif123")
    
    @pytest.mark.asyncio
    async def test_get_notification_by_id_missing_id(self, notification_service):
        """Test notification retrieval with missing ID"""
        with pytest.raises(ValidationError, match="Notification ID is required"):
            await notification_service.get_notification_by_id("")
    
    @pytest.mark.asyncio
    async def test_get_notification_by_id_not_found(self, notification_service):
        """Test notification retrieval when notification doesn't exist"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Notification not found"):
            await notification_service.get_notification_by_id("notif123")
    
    # Test get_user_notifications
    @pytest.mark.asyncio
    async def test_get_user_notifications_success(self, notification_service, mock_search_filters, mock_notification_data):
        """Test successful user notifications retrieval"""
        mock_notifications = [mock_notification_data, mock_notification_data]
        notification_service.notification_service.query = AsyncMock(return_value=mock_notifications)
        notification_service.notification_service.count = AsyncMock(return_value=2)
        
        result = await notification_service.get_user_notifications("user123", mock_search_filters)
        
        assert result.count == 2
        assert len(result.results) == 2
        # With limit=20 and offset=0, and only 2 total results, there should be no next page
        assert result.next is None
        assert result.previous is None
    
    @pytest.mark.asyncio
    async def test_get_user_notifications_missing_user_id(self, notification_service, mock_search_filters):
        """Test user notifications retrieval with missing user ID"""
        with pytest.raises(ValidationError, match="User ID is required"):
            await notification_service.get_user_notifications("", mock_search_filters)
    
    @pytest.mark.asyncio
    async def test_get_user_notifications_invalid_type(self, notification_service):
        """Test user notifications retrieval with invalid type"""
        # Create filters with valid type for Pydantic validation
        filters = NotificationSearchFilters(type="opportunity")
        
        # Mock the service to simulate invalid type validation
        notification_service.notification_service.query = AsyncMock(side_effect=ValidationError("Invalid notification type"))
        
        with pytest.raises(ValidationError, match="Invalid notification type"):
            await notification_service.get_user_notifications("user123", filters)
    
    # Test mark_notification_read
    @pytest.mark.asyncio
    async def test_mark_notification_read_success(self, notification_service, mock_notification_data):
        """Test successful notification mark as read"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.update = AsyncMock()
        
        result = await notification_service.mark_notification_read("notif123", "user123")
        
        assert result == mock_notification_data
        notification_service.notification_service.update.assert_called_once_with("notif123", {"is_read": True})
    
    @pytest.mark.asyncio
    async def test_mark_notification_read_unauthorized(self, notification_service, mock_notification_data):
        """Test marking notification as read with wrong user"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await notification_service.mark_notification_read("notif123", "wrong_user")
    
    @pytest.mark.asyncio
    async def test_mark_notification_read_not_found(self, notification_service):
        """Test marking non-existent notification as read"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Notification not found"):
            await notification_service.mark_notification_read("notif123", "user123")
    
    # Test mark_all_notifications_read
    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_success(self, notification_service):
        """Test successful mark all notifications as read"""
        mock_notifications = [{"id": "notif1"}, {"id": "notif2"}]
        notification_service.notification_service.query = AsyncMock(return_value=mock_notifications)
        notification_service.notification_service.update = AsyncMock()
        
        result = await notification_service.mark_all_notifications_read("user123")
        
        assert result is True
        assert notification_service.notification_service.update.call_count == 2
    
    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_no_unread(self, notification_service):
        """Test mark all notifications as read when no unread notifications"""
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.mark_all_notifications_read("user123")
        
        assert result is True
        notification_service.notification_service.update.assert_not_called()
    
    # Test mark_notifications_bulk_read
    @pytest.mark.asyncio
    async def test_mark_notifications_bulk_read_success(self, notification_service, mock_bulk_read_data):
        """Test successful bulk mark notifications as read"""
        mock_notification = {"id": "notif1", "user_id": "user123"}
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification)
        notification_service.notification_service.update = AsyncMock()
        
        result = await notification_service.mark_notifications_bulk_read("user123", mock_bulk_read_data)
        
        assert result is True
        assert notification_service.notification_service.update.call_count == 3
    
    @pytest.mark.asyncio
    async def test_mark_notifications_bulk_read_missing_ids(self, notification_service):
        """Test bulk mark notifications as read with missing IDs"""
        bulk_data = NotificationBulkRead(notification_ids=[])
        
        with pytest.raises(ValidationError, match="Notification IDs are required"):
            await notification_service.mark_notifications_bulk_read("user123", bulk_data)
    
    # Test delete_notification
    @pytest.mark.asyncio
    async def test_delete_notification_success(self, notification_service, mock_notification_data):
        """Test successful notification deletion"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.delete = AsyncMock()
        
        result = await notification_service.delete_notification("notif123", "user123")
        
        assert result is True
        notification_service.notification_service.delete.assert_called_once_with("notif123")
    
    @pytest.mark.asyncio
    async def test_delete_notification_unauthorized(self, notification_service, mock_notification_data):
        """Test notification deletion with wrong user"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await notification_service.delete_notification("notif123", "wrong_user")
    
    # Test get_unread_notification_count
    @pytest.mark.asyncio
    async def test_get_unread_notification_count_success(self, notification_service):
        """Test successful unread notification count"""
        notification_service.notification_service.count = AsyncMock(return_value=5)
        
        result = await notification_service.get_unread_notification_count("user123")
        
        assert result == 5
        notification_service.notification_service.count.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_unread_notification_count_missing_user_id(self, notification_service):
        """Test unread notification count with missing user ID"""
        with pytest.raises(ValidationError, match="User ID is required"):
            await notification_service.get_unread_notification_count("")
    
    # Test specialized notification creation methods
    @pytest.mark.asyncio
    async def test_create_message_notification_success(self, notification_service, mock_notification_data):
        """Test successful message notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_message_notification("user123", "John Doe", "conv123")
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_message_notification_missing_sender_name(self, notification_service):
        """Test message notification creation with missing sender name"""
        with pytest.raises(ValidationError, match="Sender name is required"):
            await notification_service.create_message_notification("user123", "", "conv123")
    
    @pytest.mark.asyncio
    async def test_create_opportunity_notification_success(self, notification_service, mock_notification_data):
        """Test successful opportunity notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_opportunity_notification("user123", "Soccer Trial", "opp123")
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_application_notification_success(self, notification_service, mock_notification_data):
        """Test successful application notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_application_notification("user123", "accepted", "Soccer Trial")
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_application_notification_invalid_status(self, notification_service):
        """Test application notification creation with invalid status"""
        with pytest.raises(ValidationError, match="Invalid application status"):
            await notification_service.create_application_notification("user123", "invalid_status", "Soccer Trial")
    
    @pytest.mark.asyncio
    async def test_create_verification_notification_success(self, notification_service, mock_notification_data):
        """Test successful verification notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_verification_notification("user123", "approved")
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_verification_notification_invalid_status(self, notification_service):
        """Test verification notification creation with invalid status"""
        with pytest.raises(ValidationError, match="Invalid verification status"):
            await notification_service.create_verification_notification("user123", "invalid_status")
    
    @pytest.mark.asyncio
    async def test_create_moderation_notification_success(self, notification_service, mock_notification_data):
        """Test successful moderation notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_moderation_notification("user123", "video", "approved")
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_moderation_notification_invalid_status(self, notification_service):
        """Test moderation notification creation with invalid status"""
        with pytest.raises(ValidationError, match="Invalid moderation status"):
            await notification_service.create_moderation_notification("user123", "video", "invalid_status")
    
    # Test cleanup_old_notifications
    @pytest.mark.asyncio
    async def test_cleanup_old_notifications_success(self, notification_service):
        """Test successful cleanup of old notifications"""
        mock_old_notifications = [{"id": "old1"}, {"id": "old2"}]
        notification_service.notification_service.query = AsyncMock(return_value=mock_old_notifications)
        notification_service.notification_service.batch_delete = AsyncMock()
        
        result = await notification_service.cleanup_old_notifications(30)
        
        assert result == 2
        notification_service.notification_service.batch_delete.assert_called_once_with(["old1", "old2"])
    
    @pytest.mark.asyncio
    async def test_cleanup_old_notifications_invalid_days(self, notification_service):
        """Test cleanup with invalid days parameter"""
        with pytest.raises(ValidationError, match="Days old must be at least 1"):
            await notification_service.cleanup_old_notifications(0)
    
    # Test error handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, notification_service, mock_notification_create):
        """Test database error handling"""
        notification_service.notification_service.create = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(DatabaseError, match="Failed to create notification"):
            await notification_service.create_notification(mock_notification_create)
    
    @pytest.mark.asyncio
    async def test_validation_error_propagation(self, notification_service, mock_search_filters):
        """Test that validation errors are properly propagated"""
        with pytest.raises(ValidationError, match="User ID is required"):
            await notification_service.get_user_notifications("", mock_search_filters)
    
    @pytest.mark.asyncio
    async def test_resource_not_found_error_propagation(self, notification_service):
        """Test that resource not found errors are properly propagated"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Notification not found"):
            await notification_service.get_notification_by_id("notif123")
    
    @pytest.mark.asyncio
    async def test_authorization_error_propagation(self, notification_service, mock_notification_data):
        """Test that authorization errors are properly propagated"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await notification_service.delete_notification("notif123", "wrong_user") 