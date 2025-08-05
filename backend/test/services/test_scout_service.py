"""
Tests for ScoutService
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.scout_service import ScoutService
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError
from app.models.scout import ScoutProfileCreate, ScoutProfileUpdate, ScoutSearchFilters, ScoutVerificationRequest


class TestScoutService:
    """Test cases for ScoutService"""
    
    @pytest.fixture
    def scout_service(self):
        """Create a ScoutService instance with mocked database services"""
        service = ScoutService.__new__(ScoutService)
        
        # Mock the database services
        service.scout_service = AsyncMock()
        service.user_service = AsyncMock()
        service.opportunity_service = AsyncMock()
        service.application_service = AsyncMock()
        service.scout_activity_service = AsyncMock()
        service.conversation_service = AsyncMock()
        service.message_service = AsyncMock()
        
        return service
    
    @pytest.fixture
    def mock_profile_data(self):
        """Mock scout profile data"""
        return {
            "id": "profile123",
            "user_id": "user123",
            "first_name": "John",
            "last_name": "Doe",
            "organization": "NFL Scouting",
            "title": "Senior Scout",
            "verification_status": "pending",
            "focus_areas": ["U18 Soccer", "West Coast"]
        }
    
    @pytest.fixture
    def mock_activity_data(self):
        """Mock activity tracking data"""
        return {
            "scout_id": "scout123",
            "athlete_id": "athlete456",
            "activity_type": "athlete_view",
            "timestamp": "2024-01-15T10:00:00",
            "metadata": {
                "view_source": "profile_page",
                "session_id": None
            }
        }
    
    @pytest.mark.asyncio
    async def test_create_scout_profile_success(self, scout_service, mock_profile_data):
        """Test successful scout profile creation"""
        # Mock get_by_field to return None first (for existence check), then the created profile
        scout_service.scout_service.get_by_field = AsyncMock(side_effect=[
            None,  # First call - profile doesn't exist
            {      # Second call - return created profile
                "id": "profile123",
                "user_id": "user123",
                "first_name": "John",
                "last_name": "Doe",
                "organization": "NFL Scouting",
                "title": "Senior Scout",
                "verification_status": "pending",
                "focus_areas": ["U18 Soccer", "West Coast"]
            }
        ])
        scout_service.scout_service.create = AsyncMock(return_value="profile123")
        
        profile_data = ScoutProfileCreate(
            first_name="John",
            last_name="Doe",
            organization="NFL Scouting",
            title="Senior Scout",
            focus_areas=["U18 Soccer", "West Coast"]
        )
        
        result = await scout_service.create_scout_profile("user123", profile_data)
        
        assert result["id"] == "profile123"
        assert result["user_id"] == "user123"
        assert result["verification_status"] == "pending"
        scout_service.scout_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_scout_profile_already_exists(self, scout_service):
        """Test creating scout profile when one already exists"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value={"id": "existing"})
        
        profile_data = ScoutProfileCreate(
            first_name="John",
            last_name="Doe",
            organization="NFL Scouting",
            title="Senior Scout"
        )
        
        with pytest.raises(ValidationError, match="Scout profile already exists"):
            await scout_service.create_scout_profile("user123", profile_data)
    
    @pytest.mark.asyncio
    async def test_create_scout_profile_missing_fields(self, scout_service):
        """Test creating scout profile with missing required fields"""
        profile_data = ScoutProfileCreate(
            first_name="",  # Missing required field
            last_name="Doe",
            organization="",  # Missing required field
            title="Senior Scout"
        )
        
        with pytest.raises(ValidationError, match="Missing required fields"):
            await scout_service.create_scout_profile("user123", profile_data)
    
    @pytest.mark.asyncio
    async def test_get_scout_profile_success(self, scout_service, mock_profile_data):
        """Test successful scout profile retrieval"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=mock_profile_data)
        
        result = await scout_service.get_scout_profile("user123")
        
        assert result == mock_profile_data
        scout_service.scout_service.get_by_field.assert_called_once_with("user_id", "user123")
    
    @pytest.mark.asyncio
    async def test_get_scout_profile_not_found(self, scout_service):
        """Test getting scout profile that doesn't exist"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Scout profile"):
            await scout_service.get_scout_profile("user123")
    
    @pytest.mark.asyncio
    async def test_update_scout_profile_success(self, scout_service, mock_profile_data):
        """Test successful scout profile update"""
        # Mock the original profile
        original_profile = mock_profile_data.copy()
        scout_service.scout_service.get_by_field = AsyncMock(side_effect=[
            original_profile,  # First call - existing profile
            {                  # Second call - updated profile
                **original_profile,
                "title": "Lead Scout"
            }
        ])
        scout_service.scout_service.update = AsyncMock()
        
        update_data = ScoutProfileUpdate(title="Lead Scout")
        result = await scout_service.update_scout_profile("user123", update_data)
        
        assert result["title"] == "Lead Scout"
        scout_service.scout_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_scout_profile_no_changes(self, scout_service):
        """Test updating scout profile with no valid changes"""
        update_data = ScoutProfileUpdate()  # No fields provided
        
        with pytest.raises(ValidationError, match="No valid fields provided"):
            await scout_service.update_scout_profile("user123", update_data)
    
    @pytest.mark.asyncio
    async def test_search_scouts_success(self, scout_service):
        """Test successful scout search"""
        mock_scouts = [
            {"id": "scout1", "first_name": "John", "organization": "NFL"},
            {"id": "scout2", "first_name": "Jane", "organization": "NFL"}
        ]
        
        scout_service.scout_service.query = AsyncMock(return_value=mock_scouts)
        scout_service.scout_service.count = AsyncMock(return_value=2)
        
        filters = ScoutSearchFilters(organization="NFL", limit=10, offset=0)
        result = await scout_service.search_scouts(filters)
        
        assert result.count == 2
        assert len(result.results) == 2
        assert result.results == mock_scouts
    
    @pytest.mark.asyncio
    async def test_get_scout_opportunities_success(self, scout_service):
        """Test getting scout opportunities"""
        mock_opportunities = [
            {"id": "opp1", "title": "Trial Opportunity"},
            {"id": "opp2", "title": "Scholarship Opportunity"}
        ]
        
        scout_service.opportunity_service.query = AsyncMock(return_value=mock_opportunities)
        
        result = await scout_service.get_scout_opportunities("scout123")
        
        assert result == mock_opportunities
        scout_service.opportunity_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_track_athlete_view_success(self, scout_service):
        """Test successful athlete view tracking"""
        scout_service.scout_activity_service.create = AsyncMock(return_value="activity123")
        
        result = await scout_service.track_athlete_view("scout123", "athlete456")
        
        assert result is True
        scout_service.scout_activity_service.create.assert_called_once()
        
        # Verify the activity data structure
        call_args = scout_service.scout_activity_service.create.call_args[0][0]
        assert call_args["scout_id"] == "scout123"
        assert call_args["athlete_id"] == "athlete456"
        assert call_args["activity_type"] == "athlete_view"
        assert "timestamp" in call_args
        assert call_args["metadata"]["view_source"] == "profile_page"
    
    @pytest.mark.asyncio
    async def test_track_athlete_view_missing_params(self, scout_service):
        """Test athlete view tracking with missing parameters"""
        with pytest.raises(ValidationError, match="Scout ID and Athlete ID are required"):
            await scout_service.track_athlete_view("", "athlete456")
        
        with pytest.raises(ValidationError, match="Scout ID and Athlete ID are required"):
            await scout_service.track_athlete_view("scout123", "")
    
    @pytest.mark.asyncio
    async def test_track_search_performed_success(self, scout_service):
        """Test successful search tracking"""
        scout_service.scout_activity_service.create = AsyncMock(return_value="activity123")
        
        filters = {"sport": "soccer", "age_min": 18}
        result = await scout_service.track_search_performed("scout123", "athletes", "soccer players", filters)
        
        assert result is True
        scout_service.scout_activity_service.create.assert_called_once()
        
        # Verify the activity data structure
        call_args = scout_service.scout_activity_service.create.call_args[0][0]
        assert call_args["scout_id"] == "scout123"
        assert call_args["activity_type"] == "search_performed"
        assert call_args["search_type"] == "athletes"
        assert call_args["query"] == "soccer players"
        assert call_args["filters"] == filters
        assert "timestamp" in call_args
    
    @pytest.mark.asyncio
    async def test_track_message_sent_success(self, scout_service):
        """Test successful message tracking"""
        scout_service.scout_activity_service.create = AsyncMock(return_value="activity123")
        
        result = await scout_service.track_message_sent("scout123", "conv456", "msg789", "athlete101")
        
        assert result is True
        scout_service.scout_activity_service.create.assert_called_once()
        
        # Verify the activity data structure
        call_args = scout_service.scout_activity_service.create.call_args[0][0]
        assert call_args["scout_id"] == "scout123"
        assert call_args["activity_type"] == "message_sent"
        assert call_args["conversation_id"] == "conv456"
        assert call_args["message_id"] == "msg789"
        assert call_args["recipient_id"] == "athlete101"
        assert "timestamp" in call_args
    
    @pytest.mark.asyncio
    async def test_get_scout_analytics_with_tracking(self, scout_service):
        """Test getting scout analytics with real tracking data"""
        # Mock counts for different analytics
        scout_service.opportunity_service.count = AsyncMock(return_value=5)
        scout_service.application_service.count = AsyncMock(return_value=12)
        scout_service.scout_activity_service.count = AsyncMock(side_effect=[8, 15, 23])  # views, searches, messages
        
        result = await scout_service.get_scout_analytics("scout123")
        
        assert result.athletes_viewed == 8
        assert result.searches_performed == 15
        assert result.opportunities_created == 5
        assert result.applications_received == 12
        assert result.messages_sent == 23
        
        # Verify the correct filters were used
        assert scout_service.scout_activity_service.count.call_count == 3
    
    @pytest.mark.asyncio
    async def test_get_scout_analytics_no_activities(self, scout_service):
        """Test getting scout analytics when no activities exist"""
        scout_service.opportunity_service.count = AsyncMock(return_value=0)
        scout_service.application_service.count = AsyncMock(return_value=0)
        scout_service.scout_activity_service.count = AsyncMock(return_value=0)
        
        result = await scout_service.get_scout_analytics("scout123")
        
        assert result.athletes_viewed == 0
        assert result.searches_performed == 0
        assert result.opportunities_created == 0
        assert result.applications_received == 0
        assert result.messages_sent == 0
    
    @pytest.mark.asyncio
    async def test_get_scout_activity_summary_success(self, scout_service):
        """Test getting scout activity summary"""
        mock_activities = [
            {"activity_type": "athlete_view", "athlete_id": "athlete1"},
            {"activity_type": "athlete_view", "athlete_id": "athlete2"},
            {"activity_type": "search_performed", "query": "soccer"},
            {"activity_type": "message_sent", "message_id": "msg1"},
            {"activity_type": "message_sent", "message_id": "msg2"}
        ]
        
        scout_service.scout_activity_service.query = AsyncMock(return_value=mock_activities)
        
        result = await scout_service.get_scout_activity_summary("scout123", days=30)
        
        assert result["total_activities"] == 5
        assert result["athlete_views_count"] == 2
        assert result["searches_count"] == 1
        assert result["messages_count"] == 2
        assert len(result["athlete_views"]) == 2
        assert len(result["searches"]) == 1
        assert len(result["messages"]) == 2
    
    @pytest.mark.asyncio
    async def test_verify_scout_success(self, scout_service, mock_profile_data):
        """Test successful scout verification"""
        # Mock the original profile
        original_profile = mock_profile_data.copy()
        scout_service.scout_service.get_by_field = AsyncMock(side_effect=[
            original_profile,  # First call - existing profile
            {                  # Second call - updated profile
                **original_profile,
                "verification_status": "verified",
                "verification_notes": "Approved"
            }
        ])
        scout_service.scout_service.update = AsyncMock()
        
        verification_data = ScoutVerificationRequest(status="verified", notes="Approved")
        result = await scout_service.verify_scout("scout123", verification_data)
        
        assert result["verification_status"] == "verified"
        scout_service.scout_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_scout_not_found(self, scout_service):
        """Test verifying scout that doesn't exist"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=None)
        
        verification_data = ScoutVerificationRequest(status="verified")
        
        with pytest.raises(ResourceNotFoundError, match="Scout profile"):
            await scout_service.verify_scout("scout123", verification_data)
    
    @pytest.mark.asyncio
    async def test_delete_scout_profile_success(self, scout_service, mock_profile_data):
        """Test successful scout profile deletion"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=mock_profile_data)
        scout_service.scout_service.delete = AsyncMock()
        
        result = await scout_service.delete_scout_profile("user123")
        
        assert result is True
        scout_service.scout_service.delete.assert_called_once_with("profile123")
    
    @pytest.mark.asyncio
    async def test_delete_scout_profile_not_found(self, scout_service):
        """Test deleting scout profile that doesn't exist"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Scout profile"):
            await scout_service.delete_scout_profile("user123")
    
    @pytest.mark.asyncio
    async def test_get_pending_verifications_success(self, scout_service):
        """Test getting pending verifications"""
        mock_pending = [
            {"id": "scout1", "verification_status": "pending"},
            {"id": "scout2", "verification_status": "pending"}
        ]
        
        scout_service.scout_service.query = AsyncMock(return_value=mock_pending)
        scout_service.scout_service.count = AsyncMock(return_value=2)
        
        result = await scout_service.get_pending_verifications(limit=10, offset=0)
        
        assert result.count == 2
        assert len(result.results) == 2
        assert result.results == mock_pending
    
    @pytest.mark.asyncio
    async def test_error_handling_database_errors(self, scout_service):
        """Test proper error handling for database errors"""
        scout_service.scout_service.get_by_field = AsyncMock(side_effect=Exception("Database connection failed"))
        
        with pytest.raises(DatabaseError, match="Failed to get scout profile"):
            await scout_service.get_scout_profile("user123")
    
    @pytest.mark.asyncio
    async def test_error_handling_validation_errors(self, scout_service):
        """Test proper error handling for validation errors"""
        with pytest.raises(ValidationError, match="User ID is required"):
            await scout_service.get_scout_profile("")
    
    @pytest.mark.asyncio
    async def test_error_handling_resource_not_found(self, scout_service):
        """Test proper error handling for resource not found"""
        scout_service.scout_service.get_by_field = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Scout profile"):
            await scout_service.get_scout_profile("user123") 