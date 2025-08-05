import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, date, timezone
from datetime import timedelta

from app.services.opportunity_service import OpportunityService
from app.models.opportunity import OpportunityCreate, OpportunityUpdate, OpportunitySearchFilters, OpportunityToggleRequest
from app.models.application import ApplicationCreate, ApplicationStatusUpdate
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError


class TestOpportunityService:
    """Test cases for OpportunityService"""
    
    @pytest.fixture
    def opportunity_service(self):
        service = OpportunityService.__new__(OpportunityService)
        service.opportunity_service = AsyncMock()
        service.application_service = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_opportunity_data(self):
        return {
            "id": "opp123",
            "scout_id": "scout123",
            "title": "NFL Quarterback Opportunity",
            "description": "Looking for talented quarterbacks",
            "type": "trial",
            "sport_category_id": "football123",
            "location": "New York",
            "start_date": "2024-06-01",
            "end_date": "2024-08-01",
            "requirements": "Strong arm, leadership skills",
            "compensation": "$50,000",
            "is_active": True,
            "moderation_status": "pending"
        }
    
    @pytest.fixture
    def mock_application_data(self):
        return {
            "id": "app123",
            "opportunity_id": "opp123",
            "athlete_id": "athlete123",
            "status": "pending",
            "cover_letter": "I'm interested in this opportunity",
            "resume_url": "https://example.com/resume.pdf",
            "applied_at": datetime.now(timezone.utc),
            "status_updated_at": None
        }
    
    @pytest.mark.asyncio
    async def test_create_opportunity_success(self, opportunity_service, mock_opportunity_data):
        """Test successful opportunity creation"""
        opportunity_service.opportunity_service.create = AsyncMock(return_value="opp123")
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        
        opportunity_data = OpportunityCreate(
            title="NFL Quarterback Opportunity",
            description="Looking for talented quarterbacks",
            type="trial",
            sport_category_id="football123",
            location="New York",
            start_date=date(2024, 6, 1),
            end_date=date(2024, 8, 1),
            requirements="Strong arm, leadership skills",
            compensation="$50,000"
        )
        
        result = await opportunity_service.create_opportunity("scout123", opportunity_data)
        
        assert result is not None
        assert result["id"] == "opp123"
        opportunity_service.opportunity_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_opportunity_missing_scout_id(self, opportunity_service):
        """Test opportunity creation with missing scout ID"""
        opportunity_data = OpportunityCreate(
            title="Test Opportunity",
            description="Test description",
            type="trial",
            sport_category_id="sport123",
            location="Test Location",
            start_date=date(2024, 6, 1)
        )
        
        with pytest.raises(ValidationError, match="Scout ID is required"):
            await opportunity_service.create_opportunity("", opportunity_data)
    
    @pytest.mark.asyncio
    async def test_create_opportunity_invalid_date_range(self, opportunity_service):
        """Test opportunity creation with invalid date range"""
        opportunity_data = OpportunityCreate(
            title="Test Opportunity",
            description="Test description",
            type="trial",
            sport_category_id="sport123",
            location="Test Location",
            start_date=date(2024, 8, 1),
            end_date=date(2024, 6, 1)  # End before start
        )
        
        with pytest.raises(ValidationError, match="End date cannot be before start date"):
            await opportunity_service.create_opportunity("scout123", opportunity_data)
    
    @pytest.mark.asyncio
    async def test_get_opportunity_by_id_success(self, opportunity_service, mock_opportunity_data):
        """Test successful opportunity retrieval"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        
        result = await opportunity_service.get_opportunity_by_id("opp123")
        
        assert result is not None
        assert result["id"] == "opp123"
        assert isinstance(result["start_date"], date)
        assert isinstance(result["end_date"], date)
    
    @pytest.mark.asyncio
    async def test_get_opportunity_by_id_not_found(self, opportunity_service):
        """Test opportunity retrieval when not found"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Opportunity"):
            await opportunity_service.get_opportunity_by_id("nonexistent")
    
    @pytest.mark.asyncio
    async def test_get_opportunity_by_id_missing_id(self, opportunity_service):
        """Test opportunity retrieval with missing ID"""
        with pytest.raises(ValidationError, match="Opportunity ID is required"):
            await opportunity_service.get_opportunity_by_id("")
    
    @pytest.mark.asyncio
    async def test_update_opportunity_success(self, opportunity_service, mock_opportunity_data):
        """Test successful opportunity update"""
        updated_data = mock_opportunity_data.copy()
        updated_data["title"] = "Updated Title"
        
        opportunity_service.opportunity_service.get_by_id = AsyncMock(side_effect=[
            mock_opportunity_data,  # First call for ownership check
            updated_data            # Second call after update
        ])
        opportunity_service.opportunity_service.update = AsyncMock()
        
        update_data = OpportunityUpdate(title="Updated Title")
        result = await opportunity_service.update_opportunity("opp123", update_data, "scout123")
        
        assert result["title"] == "Updated Title"
        opportunity_service.opportunity_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_opportunity_unauthorized(self, opportunity_service, mock_opportunity_data):
        """Test opportunity update by unauthorized user"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        
        update_data = OpportunityUpdate(title="Updated Title")
        
        with pytest.raises(ValidationError, match="Not authorized"):
            await opportunity_service.update_opportunity("opp123", update_data, "different_scout")
    
    @pytest.mark.asyncio
    async def test_update_opportunity_no_changes(self, opportunity_service):
        """Test opportunity update with no changes"""
        update_data = OpportunityUpdate()  # No fields set
        
        with pytest.raises(ValidationError, match="No valid fields provided"):
            await opportunity_service.update_opportunity("opp123", update_data)
    
    @pytest.mark.asyncio
    async def test_delete_opportunity_success(self, opportunity_service, mock_opportunity_data):
        """Test successful opportunity deletion"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        opportunity_service.opportunity_service.delete = AsyncMock()
        
        result = await opportunity_service.delete_opportunity("opp123", "scout123")
        
        assert result is True
        opportunity_service.opportunity_service.delete.assert_called_once_with("opp123")
    
    @pytest.mark.asyncio
    async def test_delete_opportunity_unauthorized(self, opportunity_service, mock_opportunity_data):
        """Test opportunity deletion by unauthorized user"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        
        with pytest.raises(ValidationError, match="Not authorized"):
            await opportunity_service.delete_opportunity("opp123", "different_scout")
    
    @pytest.mark.asyncio
    async def test_search_opportunities_success(self, opportunity_service):
        """Test successful opportunity search"""
        mock_opportunities = [
            {"id": "opp1", "title": "NFL QB", "start_date": "2024-06-01"},
            {"id": "opp2", "title": "NBA PG", "start_date": "2024-07-01"}
        ]
        
        opportunity_service.opportunity_service.query = AsyncMock(return_value=mock_opportunities)
        opportunity_service.opportunity_service.count = AsyncMock(return_value=2)
        
        filters = OpportunitySearchFilters(type="trial", location="New York")
        result = await opportunity_service.search_opportunities(filters)
        
        assert result.count == 2
        assert len(result.results) == 2
        assert all(isinstance(opp["start_date"], date) for opp in result.results)
    
    @pytest.mark.asyncio
    async def test_toggle_opportunity_status_success(self, opportunity_service, mock_opportunity_data):
        """Test successful opportunity status toggle"""
        updated_data = mock_opportunity_data.copy()
        updated_data["is_active"] = False
        
        opportunity_service.opportunity_service.get_by_id = AsyncMock(side_effect=[
            mock_opportunity_data,  # First call for ownership check
            updated_data            # Second call after update
        ])
        opportunity_service.opportunity_service.update = AsyncMock()
        
        toggle_data = OpportunityToggleRequest(is_active=False)
        result = await opportunity_service.toggle_opportunity_status("opp123", toggle_data, "scout123")
        
        assert result["is_active"] is False
        opportunity_service.opportunity_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_for_opportunity_success(self, opportunity_service, mock_opportunity_data, mock_application_data):
        """Test successful application for opportunity"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        opportunity_service.application_service.get_by_field_list = AsyncMock(return_value=[])
        opportunity_service.application_service.create = AsyncMock(return_value="app123")
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=mock_application_data)
        
        application_data = ApplicationCreate(
            cover_letter="I'm interested in this opportunity",
            resume_url="https://example.com/resume.pdf"
        )
        
        result = await opportunity_service.apply_for_opportunity("opp123", "athlete123", application_data)
        
        assert result is not None
        assert result["id"] == "app123"
        opportunity_service.application_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_apply_for_opportunity_already_applied(self, opportunity_service, mock_opportunity_data):
        """Test application when already applied"""
        existing_applications = [{"athlete_id": "athlete123"}]
        
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        opportunity_service.application_service.get_by_field_list = AsyncMock(return_value=existing_applications)
        
        application_data = ApplicationCreate(cover_letter="Test")
        
        with pytest.raises(ValidationError, match="Already applied"):
            await opportunity_service.apply_for_opportunity("opp123", "athlete123", application_data)
    
    @pytest.mark.asyncio
    async def test_apply_for_opportunity_inactive(self, opportunity_service):
        """Test application for inactive opportunity"""
        inactive_opportunity = {
            "id": "opp123",
            "is_active": False
        }
        
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=inactive_opportunity)
        
        application_data = ApplicationCreate(cover_letter="Test")
        
        with pytest.raises(ValidationError, match="Opportunity is not active"):
            await opportunity_service.apply_for_opportunity("opp123", "athlete123", application_data)
    
    @pytest.mark.asyncio
    async def test_get_opportunity_applications_success(self, opportunity_service, mock_opportunity_data):
        """Test successful retrieval of opportunity applications"""
        mock_applications = [
            {"id": "app1", "athlete_id": "athlete1"},
            {"id": "app2", "athlete_id": "athlete2"}
        ]
        
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        opportunity_service.application_service.query = AsyncMock(return_value=mock_applications)
        
        result = await opportunity_service.get_opportunity_applications("opp123", "scout123")
        
        assert len(result) == 2
        opportunity_service.application_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_opportunity_applications_unauthorized(self, opportunity_service, mock_opportunity_data):
        """Test unauthorized access to opportunity applications"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        
        with pytest.raises(ValidationError, match="Not authorized"):
            await opportunity_service.get_opportunity_applications("opp123", "different_scout")
    
    @pytest.mark.asyncio
    async def test_get_application_by_id_success(self, opportunity_service, mock_application_data):
        """Test successful application retrieval"""
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=mock_application_data)
        
        result = await opportunity_service.get_application_by_id("app123")
        
        assert result is not None
        assert result["id"] == "app123"
    
    @pytest.mark.asyncio
    async def test_get_application_by_id_not_found(self, opportunity_service):
        """Test application retrieval when not found"""
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Application"):
            await opportunity_service.get_application_by_id("nonexistent")
    
    @pytest.mark.asyncio
    async def test_update_application_status_success(self, opportunity_service, mock_application_data, mock_opportunity_data):
        """Test successful application status update"""
        updated_application = mock_application_data.copy()
        updated_application["status"] = "accepted"
        
        opportunity_service.application_service.get_by_id = AsyncMock(side_effect=[
            mock_application_data,  # First call for authorization check
            updated_application     # Second call after update
        ])
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=mock_opportunity_data)
        opportunity_service.application_service.update = AsyncMock()
        
        status_data = ApplicationStatusUpdate(status="accepted", feedback="Great candidate!")
        result = await opportunity_service.update_application_status("app123", status_data, "scout123")
        
        assert result["status"] == "accepted"
        opportunity_service.application_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_application_status_unauthorized(self, opportunity_service, mock_application_data):
        """Test unauthorized application status update"""
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=mock_application_data)
        
        status_data = ApplicationStatusUpdate(status="accepted")
        
        with pytest.raises(ValidationError, match="Not authorized"):
            await opportunity_service.update_application_status("app123", status_data, "different_scout")
    
    @pytest.mark.asyncio
    async def test_withdraw_application_success(self, opportunity_service, mock_application_data):
        """Test successful application withdrawal"""
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=mock_application_data)
        opportunity_service.application_service.update = AsyncMock()
        
        result = await opportunity_service.withdraw_application("app123", "athlete123")
        
        assert result is True
        opportunity_service.application_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_withdraw_application_unauthorized(self, opportunity_service, mock_application_data):
        """Test unauthorized application withdrawal"""
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=mock_application_data)
        
        with pytest.raises(ValidationError, match="Not authorized"):
            await opportunity_service.withdraw_application("app123", "different_athlete")
    
    @pytest.mark.asyncio
    async def test_withdraw_application_already_withdrawn(self, opportunity_service):
        """Test withdrawal of already withdrawn application"""
        withdrawn_application = {
            "id": "app123",
            "athlete_id": "athlete123",
            "status": "withdrawn"
        }
        
        opportunity_service.application_service.get_by_id = AsyncMock(return_value=withdrawn_application)
        
        with pytest.raises(ValidationError, match="already withdrawn"):
            await opportunity_service.withdraw_application("app123", "athlete123")
    
    @pytest.mark.asyncio
    async def test_get_athlete_applications_success(self, opportunity_service):
        """Test successful retrieval of athlete applications"""
        mock_applications = [
            {"id": "app1", "opportunity_id": "opp1"},
            {"id": "app2", "opportunity_id": "opp2"}
        ]
        
        opportunity_service.application_service.query = AsyncMock(return_value=mock_applications)
        
        result = await opportunity_service.get_athlete_applications("athlete123")
        
        assert len(result) == 2
        opportunity_service.application_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_scout_opportunities_success(self, opportunity_service):
        """Test successful retrieval of scout opportunities"""
        mock_opportunities = [
            {"id": "opp1", "title": "Opportunity 1", "start_date": "2024-06-01"},
            {"id": "opp2", "title": "Opportunity 2", "start_date": "2024-07-01"}
        ]
        
        opportunity_service.opportunity_service.query = AsyncMock(return_value=mock_opportunities)
        
        result = await opportunity_service.get_scout_opportunities("scout123")
        
        assert len(result) == 2
        assert all(isinstance(opp["start_date"], date) for opp in result)
        opportunity_service.opportunity_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_database_errors(self, opportunity_service):
        """Test proper handling of database errors"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(DatabaseError, match="Failed to get opportunity"):
            await opportunity_service.get_opportunity_by_id("opp123")
    
    @pytest.mark.asyncio
    async def test_error_handling_validation_errors(self, opportunity_service):
        """Test proper handling of validation errors"""
        with pytest.raises(ValidationError, match="Opportunity ID is required"):
            await opportunity_service.get_opportunity_by_id("")
    
    @pytest.mark.asyncio
    async def test_error_handling_resource_not_found(self, opportunity_service):
        """Test proper handling of resource not found errors"""
        opportunity_service.opportunity_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Opportunity"):
            await opportunity_service.get_opportunity_by_id("nonexistent") 