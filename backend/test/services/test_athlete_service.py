import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from app.services.athlete_service import AthleteService
from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)


class TestAthleteService:
    """Test cases for AthleteService"""
    
    @pytest.mark.asyncio
    async def test_create_athlete_profile(self, mock_athlete_service):
        """Test creating athlete profile"""
        profile_data = {
            "first_name": "John",
            "last_name": "Doe",
            "sport": "football",
            "position": "quarterback",
            "age": 22,
            "height": 185,
            "weight": 85
        }
        
        # Mock successful profile creation
        mock_athlete_service.database_service.create_document.return_value = {
            "user_id": "user123",
            **profile_data,
            "created_at": datetime.now().isoformat()
        }
        
        result = await mock_athlete_service.create_profile("user123", profile_data)
        
        assert result is not None
        assert result["user_id"] == "user123"
        assert result["sport"] == "football"
        mock_athlete_service.database_service.create_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_athlete_profile(self, mock_athlete_service):
        """Test getting athlete profile"""
        # Mock existing athlete
        mock_athlete_service.database_service.get_document.return_value = {
            "user_id": "user123",
            "first_name": "John",
            "last_name": "Doe",
            "sport": "football",
            "position": "quarterback"
        }
        
        result = await mock_athlete_service.get_profile_by_user_id("user123")
        
        assert result["first_name"] == "John"
        assert result["sport"] == "football"
        assert result["position"] == "quarterback"
    
    @pytest.mark.asyncio
    async def test_search_athletes(self, mock_athlete_service):
        """Test searching athletes"""
        # Mock search results
        mock_athlete_service.database_service.query_documents.return_value = [
            {"user_id": "user1", "first_name": "John", "sport": "football"},
            {"user_id": "user2", "first_name": "Jane", "sport": "basketball"}
        ]
        mock_athlete_service.database_service.count_documents.return_value = 2
        
        filters = {"sport": "football", "position": "quarterback"}
        result = await mock_athlete_service.search_athletes(filters, page=1, limit=10)
        
        assert len(result["athletes"]) == 2
        assert result["total"] == 2
        assert result["page"] == 1
        assert result["limit"] == 10
    
    @pytest.mark.asyncio
    async def test_update_athlete_profile(self, mock_athlete_service):
        """Test updating athlete profile"""
        update_data = {"position": "running_back", "weight": 90}
        
        # Mock existing profile
        mock_athlete_service.database_service.get_document.return_value = {
            "user_id": "user123",
            "first_name": "John",
            "position": "quarterback"
        }
        
        # Mock update operation
        mock_athlete_service.database_service.update_document.return_value = AsyncMock()
        
        result = await mock_athlete_service.update_profile("user123", update_data)
        
        assert result is not None
        mock_athlete_service.database_service.update_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_athlete_stats(self, mock_athlete_service):
        """Test getting athlete statistics"""
        # Mock stats data
        mock_athlete_service.database_service.get_document.return_value = {
            "user_id": "user123",
            "stats": {
                "games_played": 25,
                "touchdowns": 15,
                "passing_yards": 3500,
                "completion_rate": 0.68
            }
        }
        
        result = await mock_athlete_service.get_stats("user123")
        
        assert result["games_played"] == 25
        assert result["touchdowns"] == 15
        assert result["passing_yards"] == 3500
    
    @pytest.mark.asyncio
    async def test_update_athlete_stats(self, mock_athlete_service):
        """Test updating athlete statistics"""
        stats_data = {
            "games_played": 26,
            "touchdowns": 16,
            "passing_yards": 3650
        }
        
        # Mock stats update
        mock_athlete_service.database_service.update_document.return_value = AsyncMock()
        mock_athlete_service.database_service.get_document.return_value = {
            "user_id": "user123",
            "stats": stats_data
        }
        
        result = await mock_athlete_service.update_stats("user123", stats_data)
        
        assert result["stats"]["games_played"] == 26
        assert result["stats"]["touchdowns"] == 16
        mock_athlete_service.database_service.update_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_athlete_media(self, mock_athlete_service):
        """Test getting athlete media"""
        # Mock media data
        mock_athlete_service.database_service.query_documents.return_value = [
            {"id": "media1", "title": "Game Highlights", "type": "video"},
            {"id": "media2", "title": "Training Session", "type": "video"}
        ]
        
        result = await mock_athlete_service.get_media("user123", page=1, limit=10)
        
        assert len(result) == 2
        assert result[0]["title"] == "Game Highlights"
        assert result[1]["title"] == "Training Session"
    
    @pytest.mark.asyncio
    async def test_get_athlete_analytics(self, mock_athlete_service):
        """Test getting athlete analytics"""
        # Mock analytics data
        mock_athlete_service.database_service.query_documents.return_value = [
            {"metric": "profile_views", "value": 150, "date": "2024-01-15"},
            {"metric": "media_views", "value": 85, "date": "2024-01-15"}
        ]
        
        result = await mock_athlete_service.get_analytics("user123")
        
        assert len(result) == 2
        assert result[0]["metric"] == "profile_views"
        assert result[0]["value"] == 150
    
    @pytest.mark.asyncio
    async def test_get_athlete_recommendations(self, mock_athlete_service):
        """Test getting athlete recommendations"""
        # Mock recommendations
        mock_athlete_service.database_service.query_documents.return_value = [
            {"id": "opp1", "title": "NFL Tryout", "type": "trial", "match_score": 0.95},
            {"id": "opp2", "title": "College Scholarship", "type": "scholarship", "match_score": 0.87}
        ]
        
        result = await mock_athlete_service.get_recommendations("user123", sport="football")
        
        assert len(result) == 2
        assert result[0]["title"] == "NFL Tryout"
        assert result[0]["match_score"] == 0.95
    
    @pytest.mark.asyncio
    async def test_add_achievement(self, mock_athlete_service):
        """Test adding athlete achievement"""
        achievement_data = {
            "type": "championship",
            "title": "State Championship Winner",
            "description": "Won state championship with team",
            "date_achieved": "2024-01-01"
        }
        
        # Mock achievement creation
        mock_athlete_service.database_service.create_document.return_value = {
            "id": "achievement123",
            "athlete_id": "user123",
            **achievement_data
        }
        
        result = await mock_athlete_service.add_achievement("user123", achievement_data)
        
        assert result["title"] == "State Championship Winner"
        assert result["type"] == "championship"
        mock_athlete_service.database_service.create_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_athlete_achievements(self, mock_athlete_service):
        """Test getting athlete achievements"""
        # Mock achievements
        mock_athlete_service.database_service.query_documents.return_value = [
            {"id": "ach1", "title": "MVP Award", "type": "individual"},
            {"id": "ach2", "title": "Team Captain", "type": "leadership"}
        ]
        
        result = await mock_athlete_service.get_achievements("user123")
        
        assert len(result) == 2
        assert result[0]["title"] == "MVP Award"
        assert result[1]["title"] == "Team Captain"
    
    @pytest.mark.asyncio
    async def test_verify_athlete_profile(self, mock_athlete_service):
        """Test verifying athlete profile"""
        verification_data = {
            "document_type": "student_id",
            "document_url": "https://example.com/student_id.jpg",
            "additional_info": "Current university student"
        }
        
        # Mock verification submission
        mock_athlete_service.database_service.create_document.return_value = {
            "id": "verification123",
            "user_id": "user123",
            "status": "pending",
            **verification_data
        }
        
        result = await mock_athlete_service.submit_verification("user123", verification_data)
        
        assert result["status"] == "pending"
        assert result["document_type"] == "student_id"
        mock_athlete_service.database_service.create_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_athletes_by_sport_and_location(self, mock_athlete_service):
        """Test searching athletes with specific filters"""
        # Mock search with complex filters
        mock_athlete_service.database_service.query_documents.return_value = [
            {
                "user_id": "user1", 
                "sport": "football", 
                "location": "California",
                "position": "quarterback"
            }
        ]
        mock_athlete_service.database_service.count_documents.return_value = 1
        
        filters = {
            "sport": "football",
            "location": "California",
            "position": "quarterback",
            "min_age": 18,
            "max_age": 25
        }
        
        result = await mock_athlete_service.search_athletes(filters, page=1, limit=10)
        
        assert len(result["athletes"]) == 1
        assert result["athletes"][0]["sport"] == "football"
        assert result["athletes"][0]["location"] == "California"
    
    @pytest.mark.asyncio
    async def test_get_athlete_profile_completion(self, mock_athlete_service):
        """Test calculating athlete profile completion percentage"""
        # Mock profile with some fields filled
        mock_athlete_service.database_service.get_document.return_value = {
            "user_id": "user123",
            "first_name": "John",
            "last_name": "Doe",
            "sport": "football",
            "position": "quarterback",
            "bio": None,  # Missing field
            "profile_image_url": None  # Missing field
        }
        
        result = await mock_athlete_service.calculate_profile_completion("user123")
        
        assert result["completion_percentage"] < 100
        assert "missing_fields" in result
        assert len(result["missing_fields"]) > 0
    
    @pytest.mark.asyncio
    async def test_delete_athlete_profile(self, mock_athlete_service):
        """Test deleting athlete profile"""
        # Mock profile deletion
        mock_athlete_service.database_service.delete_document.return_value = AsyncMock()
        
        result = await mock_athlete_service.delete_profile("user123")
        
        assert result["message"] == "Athlete profile deleted successfully"
        mock_athlete_service.database_service.delete_document.assert_called_once() 