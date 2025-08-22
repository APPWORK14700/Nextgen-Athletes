"""
Comprehensive test suite for NotificationService with template validation, performance monitoring, and configuration management
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from app.services.notification_service import NotificationService
from app.models.notification import (
    NotificationCreate, NotificationSearchFilters, NotificationBulkRead,
    MessageNotificationCreate, OpportunityNotificationCreate, ApplicationNotificationCreate,
    VerificationNotificationCreate, ModerationNotificationCreate,
    is_valid_notification_type, get_valid_notification_types, get_notification_templates,
    NotificationTemplates, VALID_NOTIFICATION_TYPES, NOTIFICATION_TEMPLATES
)
from app.config.notification_config import get_config_for_environment
from app.utils.performance_monitor import PerformanceMonitor
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError


class TestNotificationModels:
    """Test notification models and template validation"""
    
    def test_notification_types_constant(self):
        """Test notification types constant"""
        assert "message" in VALID_NOTIFICATION_TYPES
        assert "opportunity" in VALID_NOTIFICATION_TYPES
        assert "application" in VALID_NOTIFICATION_TYPES
        assert "verification" in VALID_NOTIFICATION_TYPES
        assert "moderation" in VALID_NOTIFICATION_TYPES
        assert len(VALID_NOTIFICATION_TYPES) == 5
    
    def test_notification_templates_constant(self):
        """Test notification templates constant"""
        assert "message" in NOTIFICATION_TEMPLATES
        assert "opportunity" in NOTIFICATION_TEMPLATES
        assert "application" in NOTIFICATION_TEMPLATES
        assert "verification" in NOTIFICATION_TEMPLATES
        assert "moderation" in NOTIFICATION_TEMPLATES
        
        # Test template structure
        message_template = NOTIFICATION_TEMPLATES["message"]
        assert "title" in message_template
        assert "message_template" in message_template
        assert "{sender_name}" in message_template["message_template"]
    
    def test_utility_functions(self):
        """Test utility functions for template management"""
        assert is_valid_notification_type("message") == True
        assert is_valid_notification_type("invalid_type") == False
        
        valid_types = get_valid_notification_types()
        assert "message" in valid_types
        assert "opportunity" in valid_types
        assert len(valid_types) == 5
        
        templates = get_notification_templates()
        assert isinstance(templates, NotificationTemplates)
        assert templates.is_valid_type("message") == True
    
    def test_template_models(self):
        """Test all template model types"""
        # Message notification
        message_data = MessageNotificationCreate(
            user_id="user123", sender_name="John Doe", conversation_id="conv456"
        )
        notification = message_data.to_notification_create()
        assert notification.type == "message"
        assert "John Doe" in notification.message
        
        # Opportunity notification
        opp_data = OpportunityNotificationCreate(
            user_id="user123", opportunity_title="Championship Tryout", opportunity_id="opp789"
        )
        notification = opp_data.to_notification_create()
        assert notification.type == "opportunity"
        assert "Championship Tryout" in notification.message
        
        # Application notification
        app_data = ApplicationNotificationCreate(
            user_id="user123", application_status="accepted", opportunity_title="Championship Tryout"
        )
        notification = app_data.to_notification_create()
        assert notification.type == "application"
        assert "accepted" in notification.message
        
        # Verification notification
        ver_data = VerificationNotificationCreate(user_id="user123", verification_status="approved")
        notification = ver_data.to_notification_create()
        assert notification.type == "verification"
        assert "approved" in notification.message
        
        # Moderation notification
        mod_data = ModerationNotificationCreate(
            user_id="user123", content_type="profile photo", moderation_status="approved"
        )
        notification = mod_data.to_notification_create()
        assert notification.type == "moderation"
        assert "profile photo" in notification.message
    
    def test_validation_errors(self):
        """Test validation errors in template models"""
        with pytest.raises(ValueError, match="Field cannot be empty"):
            MessageNotificationCreate(user_id="", sender_name="John Doe", conversation_id="conv456")
        
        with pytest.raises(ValueError, match="Invalid application status"):
            ApplicationNotificationCreate(
                user_id="user123", application_status="invalid_status", opportunity_title="Test"
            )
        
        with pytest.raises(ValueError, match="Invalid verification status"):
            VerificationNotificationCreate(user_id="user123", verification_status="invalid_status")
        
        with pytest.raises(ValueError, match="Invalid moderation status"):
            ModerationNotificationCreate(
                user_id="user123", content_type="photo", moderation_status="invalid_status"
            )
    
    def test_notification_create_validation(self):
        """Test NotificationCreate validation"""
        # Valid notification
        notification = NotificationCreate(
            user_id="user123", type="message", title="Test Title", message="Test Message"
        )
        assert notification.user_id == "user123"
        assert notification.type == "message"
        
        # Invalid notification type
        with pytest.raises(ValueError, match="Invalid notification type"):
            NotificationCreate(
                user_id="user123", type="invalid_type", title="Test Title", message="Test Message"
            )
        
        # Empty fields
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            NotificationCreate(user_id="", type="message", title="Test Title", message="Test Message")
    
    def test_search_filters_validation(self):
        """Test NotificationSearchFilters validation"""
        filters = NotificationSearchFilters(type="message", unread_only=True, limit=10, offset=0)
        assert filters.type == "message"
        assert filters.unread_only == True
        
        with pytest.raises(ValueError, match="Invalid notification type"):
            NotificationSearchFilters(type="invalid_type")
    
    def test_bulk_read_validation(self):
        """Test NotificationBulkRead validation"""
        bulk_read = NotificationBulkRead(notification_ids=["id1", "id2", "id3"])
        assert bulk_read.notification_ids == ["id1", "id2", "id3"]
        
        with pytest.raises(ValueError, match="Notification IDs cannot be empty"):
            NotificationBulkRead(notification_ids=[])
        
        with pytest.raises(ValueError, match="All notification IDs must be non-empty strings"):
            NotificationBulkRead(notification_ids=["id1", "", "id3"])


class TestNotificationService:
    """Test cases for NotificationService"""
    
    @pytest.fixture
    def mock_database_service(self):
        """Mock database service"""
        mock_service = Mock()
        mock_service.create = AsyncMock(return_value="test_notification_id")
        mock_service.get_by_id = AsyncMock(return_value={
            "id": "test_notification_id",
            "user_id": "test_user_id",
            "type": "message",
            "title": "Test Title",
            "message": "Test Message",
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        mock_service.update = AsyncMock()
        mock_service.delete = AsyncMock()
        mock_service.query = AsyncMock(return_value=[])
        mock_service.count = AsyncMock(return_value=0)
        mock_service.batch_delete = AsyncMock()
        mock_service.db = Mock()
        mock_service.collection = Mock()
        return mock_service
    
    @pytest.fixture
    def notification_service(self, mock_database_service):
        """Create notification service with mock dependencies"""
        with patch('app.services.notification_service.DatabaseService', return_value=mock_database_service):
            service = NotificationService()
            return service
    
    @pytest.fixture
    def performance_enabled_service(self, mock_database_service):
        """Create notification service with performance monitoring enabled"""
        config = {'enable_performance_monitoring': True, 'enable_metrics': True}
        with patch('app.services.notification_service.DatabaseService', return_value=mock_database_service):
            service = NotificationService(config=config)
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
        return NotificationSearchFilters(type="opportunity", unread_only=False, limit=20, offset=0)
    
    @pytest.fixture
    def mock_bulk_read_data(self):
        return NotificationBulkRead(notification_ids=["notif1", "notif2", "notif3"])
    
    def test_configuration_loading(self):
        """Test configuration loading with defaults and custom values"""
        # Default configuration
        service = NotificationService()
        assert service.max_notifications_per_user == 1000
        assert service.rate_limit_max == 50
        assert service.batch_size == 500
        assert service.enable_metrics == True
        assert service.enable_performance_monitoring == False
        
        # Custom configuration
        custom_config = {
            'max_notifications_per_user': 2000,
            'rate_limit_max': 100,
            'enable_performance_monitoring': True
        }
        service = NotificationService(config=custom_config)
        assert service.max_notifications_per_user == 2000
        assert service.rate_limit_max == 100
        assert service.enable_performance_monitoring == True
    
    def test_template_utility_methods_delegate_to_models(self, notification_service):
        """Test that template utility methods delegate to models"""
        assert notification_service.is_valid_notification_type("message") == True
        assert notification_service.is_valid_notification_type("invalid_type") == False
        
        valid_types = notification_service.get_valid_notification_types()
        assert "message" in valid_types
        assert len(valid_types) == 5
        
        templates = notification_service.get_templates()
        assert isinstance(templates, NotificationTemplates)
    
    # Test create_notification
    @pytest.mark.asyncio
    async def test_create_notification_success(self, notification_service, mock_notification_create, mock_notification_data):
        """Test successful notification creation"""
        notification_service.notification_service.create = AsyncMock(return_value="notif123")
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.count = AsyncMock(return_value=5)
        notification_service.notification_service.query = AsyncMock(return_value=[])
        
        result = await notification_service.create_notification(mock_notification_create)
        
        assert result is not None
        notification_service.notification_service.create.assert_called_once()
        
        # Check metrics were recorded
        metrics = notification_service.get_metrics()
        assert metrics['notifications_created'] == 1
    
    @pytest.mark.asyncio
    async def test_create_notification_missing_user_id(self, notification_service):
        """Test notification creation with missing user ID"""
        notification_data = NotificationCreate(
            user_id="", type="opportunity", title="New Opportunity", message="A new opportunity is available"
        )
        
        with pytest.raises(ValidationError, match="User ID cannot be empty"):
            await notification_service.create_notification(notification_data)
    
    @pytest.mark.asyncio
    async def test_create_notification_missing_title(self, notification_service):
        """Test notification creation with missing title"""
        notification_data = NotificationCreate(
            user_id="user123", type="opportunity", title="", message="A new opportunity is available"
        )
        
        with pytest.raises(ValidationError, match="Field cannot be empty"):
            await notification_service.create_notification(notification_data)
    
    @pytest.mark.asyncio
    async def test_create_notification_rate_limit_exceeded(self, notification_service, mock_notification_create):
        """Test notification creation when rate limit is exceeded"""
        notification_service.notification_service.count = AsyncMock(return_value=50)
        
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            await notification_service.create_notification(mock_notification_create)
    
    @pytest.mark.asyncio
    async def test_create_notification_with_performance_monitoring(self, performance_enabled_service, mock_notification_create):
        """Test notification creation with performance monitoring enabled"""
        result = await performance_enabled_service.create_notification(mock_notification_create)
        
        metrics = performance_enabled_service.get_metrics()
        assert metrics['notifications_created'] == 1
        assert 'total_creation_time' in metrics
        assert metrics['total_creation_time'] > 0
        
        assert result is not None
    
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
        assert result.next is None
        assert result.previous is None
    
    @pytest.mark.asyncio
    async def test_get_user_notifications_missing_user_id(self, notification_service, mock_search_filters):
        """Test user notifications retrieval with missing user ID"""
        with pytest.raises(ValidationError, match="User ID is required"):
            await notification_service.get_user_notifications("", mock_search_filters)
    
    # Test mark_notification_read
    @pytest.mark.asyncio
    async def test_mark_notification_read_success(self, notification_service, mock_notification_data):
        """Test successful notification mark as read"""
        notification_service.notification_service.get_by_id = AsyncMock(return_value=mock_notification_data)
        notification_service.notification_service.update = AsyncMock()
        
        result = await notification_service.mark_notification_read("notif123", "user123")
        
        assert result == mock_notification_data
        notification_service.notification_service.update.assert_called_once_with("notif123", {"is_read": True})
        
        # Check metrics
        metrics = notification_service.get_metrics()
        assert metrics['notifications_read'] == 1
    
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
    
    @pytest.mark.asyncio
    async def test_mark_notification_read_with_performance_monitoring(self, performance_enabled_service):
        """Test marking notification as read with performance monitoring"""
        result = await performance_enabled_service.mark_notification_read("test_id", "test_user")
        
        metrics = performance_enabled_service.get_metrics()
        assert metrics['notifications_read'] == 1
        assert 'total_read_time' in metrics
        assert 'notification_read_duration' in metrics
        
        assert result is not None
    
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
        
        # Check metrics
        metrics = notification_service.get_metrics()
        assert metrics['notifications_read'] == 2
    
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
        
        # Check metrics
        metrics = notification_service.get_metrics()
        assert metrics['notifications_read'] == 3
    
    @pytest.mark.asyncio
    async def test_mark_notifications_bulk_read_missing_ids(self, notification_service):
        """Test bulk mark notifications as read with missing IDs"""
        bulk_data = NotificationBulkRead(notification_ids=[])
        
        with pytest.raises(ValidationError, match="Notification IDs cannot be empty"):
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
        
        # Check metrics
        metrics = notification_service.get_metrics()
        assert metrics['notifications_deleted'] == 1
    
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
        with pytest.raises(ValidationError, match="Field cannot be empty"):
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
        
        # Check metrics
        metrics = notification_service.get_metrics()
        assert metrics['notifications_deleted'] == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_old_notifications_invalid_days(self, notification_service):
        """Test cleanup with invalid days parameter"""
        with pytest.raises(ValidationError, match="Days old must be at least 1"):
            await notification_service.cleanup_old_notifications(0)
    
    # Test metrics and configuration
    def test_metrics_reset_functionality(self, notification_service):
        """Test metrics reset functionality"""
        notification_service._record_metric("notifications_created", 5)
        assert notification_service.metrics['notifications_created'] == 5
        
        notification_service.reset_metrics()
        assert notification_service.metrics['notifications_created'] == 0
    
    def test_metrics_disabled_behavior(self):
        """Test behavior when metrics are disabled"""
        service = NotificationService(config={'enable_metrics': False})
        
        service._record_metric("test_counter", 1)
        assert service.metrics == {}
        
        metrics = service.get_metrics()
        assert metrics == {}
        
        service.reset_metrics()
        assert service.metrics == {}
    
    def test_batch_operations_enabled(self, notification_service):
        """Test that batch operations are properly configured"""
        assert notification_service.batch_size == 500
        assert hasattr(notification_service, '_batch_update_notifications')
    
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


class TestPerformanceMonitor:
    """Test performance monitoring functionality"""
    
    def test_performance_monitor_initialization(self):
        """Test performance monitor initialization"""
        monitor = PerformanceMonitor(threshold_ms=500, enable_logging=True)
        assert monitor.threshold_ms == 500
        assert monitor.enable_logging == True
        assert monitor.metrics == {}
    
    def test_performance_monitor_decorator(self):
        """Test performance monitor decorator"""
        monitor = PerformanceMonitor(threshold_ms=100)
        
        @monitor.monitor("test_operation")
        def test_function():
            return "success"
        
        result = test_function()
        assert result == "success"
        
        metrics = monitor.get_metrics()
        assert "test_operation" in metrics
        assert metrics["test_operation"]["total_calls"] == 1
        assert metrics["test_operation"]["successful_calls"] == 1
    
    def test_performance_monitor_async_decorator(self):
        """Test performance monitor with async functions"""
        monitor = PerformanceMonitor(threshold_ms=100)
        
        @monitor.monitor("async_test_operation")
        async def async_test_function():
            await asyncio.sleep(0.01)
            return "async_success"
        
        result = asyncio.run(async_test_function())
        assert result == "async_success"
        
        metrics = monitor.get_metrics()
        assert "async_test_operation" in metrics
        assert metrics["async_test_operation"]["total_calls"] == 1
        assert metrics["async_test_operation"]["successful_calls"] == 1
    
    def test_performance_monitor_error_tracking(self):
        """Test performance monitor tracks errors"""
        monitor = PerformanceMonitor(threshold_ms=100)
        
        @monitor.monitor("error_operation")
        def error_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            error_function()
        
        metrics = monitor.get_metrics()
        assert "error_operation" in metrics
        assert metrics["error_operation"]["total_calls"] == 1
        assert metrics["error_operation"]["failed_calls"] == 1
        assert metrics["error_operation"]["successful_calls"] == 0


class TestConfigurationManagement:
    """Test configuration management functionality"""
    
    def test_environment_specific_configs(self):
        """Test different environment configurations"""
        environments = ['development', 'production', 'testing']
        
        for env in environments:
            config = get_config_for_environment(env)
            assert 'max_notifications_per_user' in config
            assert 'rate_limit_window' in config
            assert 'batch_size' in config
            assert 'enable_metrics' in config
            assert 'enable_performance_monitoring' in config
            assert config['enable_performance_monitoring'] == False
    
    def test_config_validation(self):
        """Test configuration validation and defaults"""
        # Test with None config
        service = NotificationService(config=None)
        assert service.max_notifications_per_user == 1000
        assert service.rate_limit_max == 50
        assert service.enable_performance_monitoring == False
        
        # Test with partial config
        partial_config = {'max_notifications_per_user': 2000}
        service = NotificationService(config=partial_config)
        assert service.max_notifications_per_user == 2000
        assert service.rate_limit_max == 50
        assert service.enable_performance_monitoring == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 