"""
Tests for StatsService
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.stats_service import StatsService
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError


class TestStatsService:
    """Test cases for StatsService"""
    
    @pytest.fixture
    def stats_service(self):
        """Create a StatsService instance with mocked database services"""
        service = StatsService.__new__(StatsService)
        
        # Mock the database services
        service.stats_db = Mock()
        service.categories_db = Mock()
        
        # Initialize cache and locks
        service._cache = {}
        service._cache_lock = asyncio.Lock()
        service._cache_ttl = timedelta(minutes=15)
        service._max_cache_size = 1000
        
        return service
    
    @pytest.fixture
    def mock_stats_data(self):
        """Mock stats data"""
        return {
            "athlete_id": "athlete123",
            "sport_category_id": "soccer",
            "season": "2023-2024",
            "team_name": "FC Barcelona",
            "league": "La Liga",
            "position": "Forward",
            "stats": {
                "games_played": 25,
                "goals_scored": 15,
                "assists": 8
            },
            "achievements": [
                {
                    "type": "top_scorer",
                    "title": "Top Scorer",
                    "description": "Highest goal scorer in league",
                    "date_achieved": "2024-01-15",
                    "evidence_url": "https://example.com/evidence"
                }
            ]
        }
    
    @pytest.fixture
    def mock_sport_category(self):
        """Mock sport category data"""
        return {
            "id": "soccer",
            "name": "Soccer/Football",
            "is_active": True,
            "stats_fields": [
                {
                    "key": "games_played",
                    "label": "Games Played",
                    "type": "integer",
                    "required": True,
                    "display_order": 1
                },
                {
                    "key": "goals_scored",
                    "label": "Goals Scored",
                    "type": "integer",
                    "unit": "goals",
                    "required": False,
                    "display_order": 2
                },
                {
                    "key": "assists",
                    "label": "Assists",
                    "type": "integer",
                    "unit": "assists",
                    "required": False,
                    "display_order": 3
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_create_stats_success(self, stats_service, mock_stats_data, mock_sport_category):
        """Test successful stats creation"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        stats_service.stats_db.create = AsyncMock(return_value="stats123")
        stats_service.stats_db.get_by_id = AsyncMock(return_value={**mock_stats_data, "id": "stats123"})
        
        result = await stats_service.create_stats(mock_stats_data)
        
        assert result["id"] == "stats123"
        assert result["athlete_id"] == "athlete123"
        stats_service.stats_db.create.assert_called_once()
        stats_service.stats_db.get_by_id.assert_called_once_with("stats123")
    
    @pytest.mark.asyncio
    async def test_create_stats_missing_required_fields(self, stats_service):
        """Test stats creation with missing required fields"""
        incomplete_data = {
            "athlete_id": "athlete123",
            "sport_category_id": "soccer"
            # Missing season and stats
        }
        
        with pytest.raises(ValidationError, match="Missing required fields"):
            await stats_service.create_stats(incomplete_data)
    
    @pytest.mark.asyncio
    async def test_get_athlete_stats_with_pagination(self, stats_service, mock_stats_data):
        """Test getting athlete stats with pagination"""
        mock_records = [
            {**mock_stats_data, "id": "stats1"},
            {**mock_stats_data, "id": "stats2"}
        ]
        
        stats_service.stats_db.count = AsyncMock(return_value=2)
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        
        result = await stats_service.get_athlete_stats(
            athlete_id="athlete123",
            limit=10,
            offset=0
        )
        
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert result["limit"] == 10
        assert result["offset"] == 0
        assert result["has_next"] is False
        assert result["has_previous"] is False
    
    @pytest.mark.asyncio
    async def test_get_athlete_stats_with_cache(self, stats_service, mock_stats_data):
        """Test getting athlete stats with caching"""
        mock_records = [{**mock_stats_data, "id": "stats1"}]
        
        stats_service.stats_db.count = AsyncMock(return_value=1)
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        
        # First call - should cache
        result1 = await stats_service.get_athlete_stats("athlete123")
        
        # Second call - should use cache
        result2 = await stats_service.get_athlete_stats("athlete123")
        
        assert result1 == result2
        # Should only call database once due to caching
        assert stats_service.stats_db.count.call_count == 1
        assert stats_service.stats_db.query.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_stats_by_id_success(self, stats_service, mock_stats_data):
        """Test getting stats by ID successfully"""
        stats_service.stats_db.get_by_id = AsyncMock(return_value=mock_stats_data)
        
        result = await stats_service.get_stats_by_id("stats123")
        
        assert result == mock_stats_data
        stats_service.stats_db.get_by_id.assert_called_once_with("stats123")
    
    @pytest.mark.asyncio
    async def test_get_stats_by_id_not_found(self, stats_service):
        """Test getting stats by ID when not found"""
        stats_service.stats_db.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Stats record with ID stats123 not found"):
            await stats_service.get_stats_by_id("stats123")
    
    @pytest.mark.asyncio
    async def test_update_stats_success(self, stats_service, mock_stats_data, mock_sport_category):
        """Test successful stats update"""
        # Mock the existing record
        existing_record = mock_stats_data.copy()
        
        # Mock the updated record with the new team name
        updated_record = existing_record.copy()
        updated_record["team_name"] = "Real Madrid"
        updated_record["updated_at"] = "2024-01-15T10:00:00"
        
        stats_service.stats_db.get_by_id = AsyncMock(side_effect=[
            existing_record,  # existing record
            updated_record    # updated record
        ])
        stats_service.stats_db.update = AsyncMock()
        
        update_data = {"team_name": "Real Madrid"}
        result = await stats_service.update_stats("stats123", update_data)
        
        assert result["team_name"] == "Real Madrid"
        stats_service.stats_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_stats_success(self, stats_service, mock_stats_data):
        """Test successful stats deletion"""
        stats_service.stats_db.get_by_id = AsyncMock(return_value=mock_stats_data)
        stats_service.stats_db.delete = AsyncMock()
        
        await stats_service.delete_stats("stats123")
        
        stats_service.stats_db.delete.assert_called_once_with("stats123")
    
    @pytest.mark.asyncio
    async def test_bulk_create_stats_success(self, stats_service, mock_stats_data, mock_sport_category):
        """Test successful bulk stats creation"""
        stats_list = [mock_stats_data, {**mock_stats_data, "id": "stats2"}]
        
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        stats_service.stats_db.batch_create = AsyncMock(return_value=["stats1", "stats2"])
        stats_service.stats_db.get_by_id = AsyncMock(side_effect=[
            {**mock_stats_data, "id": "stats1"},
            {**mock_stats_data, "id": "stats2"}
        ])
        
        result = await stats_service.bulk_create_stats(stats_list)
        
        assert len(result) == 2
        assert result[0]["id"] == "stats1"
        assert result[1]["id"] == "stats2"
        stats_service.stats_db.batch_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_success(self, stats_service, mock_sport_category):
        """Test successful sport category validation"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        
        result = await stats_service.validate_sport_category("soccer")
        
        assert result == mock_sport_category
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_not_found(self, stats_service):
        """Test sport category validation when not found"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ValidationError, match="Sport category not found"):
            await stats_service.validate_sport_category("invalid_sport")
    
    @pytest.mark.asyncio
    async def test_validate_sport_category_inactive(self, stats_service):
        """Test sport category validation when inactive"""
        inactive_category = {"id": "soccer", "is_active": False}
        stats_service.categories_db.get_by_id = AsyncMock(return_value=inactive_category)
        
        with pytest.raises(ValidationError, match="Sport category is not active"):
            await stats_service.validate_sport_category("soccer")
    
    @pytest.mark.asyncio
    async def test_validate_stats_data_success(self, stats_service, mock_sport_category):
        """Test successful stats data validation"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        
        stats_data = {
            "games_played": 25,
            "goals_scored": 15,
            "assists": 8
        }
        
        # Should not raise any exception
        await stats_service.validate_stats_data("soccer", stats_data)
    
    @pytest.mark.asyncio
    async def test_validate_stats_data_invalid_field(self, stats_service, mock_sport_category):
        """Test stats data validation with invalid field"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        
        stats_data = {
            "games_played": 25,
            "invalid_field": 10  # Not in schema
        }
        
        with pytest.raises(ValidationError, match="Invalid stats field"):
            await stats_service.validate_stats_data("soccer", stats_data)
    
    @pytest.mark.asyncio
    async def test_validate_stats_data_wrong_type(self, stats_service, mock_sport_category):
        """Test stats data validation with wrong data type"""
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        
        stats_data = {
            "games_played": "25",  # Should be integer
            "goals_scored": 15
        }
        
        with pytest.raises(ValidationError, match="must be an integer"):
            await stats_service.validate_stats_data("soccer", stats_data)
    
    @pytest.mark.asyncio
    async def test_get_athlete_stats_summary(self, stats_service, mock_stats_data):
        """Test getting athlete stats summary"""
        mock_records = [mock_stats_data]
        mock_categories = [{"id": "soccer", "name": "Soccer/Football"}]
        
        stats_service.stats_db.count = AsyncMock(return_value=1)
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        stats_service.categories_db.query = AsyncMock(return_value=mock_categories)
        
        result = await stats_service.get_athlete_stats_summary("athlete123")
        
        assert result["total_seasons"] == 1
        assert len(result["sports_played"]) == 1
        assert result["achievements_count"] == 1
        assert len(result["recent_stats"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_top_performers(self, stats_service):
        """Test getting top performers"""
        mock_records = [
            {
                "athlete_id": "athlete1",
                "stats": {"goals_scored": 20},
                "season": "2023-2024",
                "team_name": "Team A"
            },
            {
                "athlete_id": "athlete2",
                "stats": {"goals_scored": 15},
                "season": "2023-2024",
                "team_name": "Team B"
            }
        ]
        
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        
        result = await stats_service.get_top_performers("soccer", "goals_scored", limit=2)
        
        assert len(result) == 2
        assert result[0]["value"] == 20  # Highest first
        assert result[1]["value"] == 15
    
    @pytest.mark.asyncio
    async def test_cache_management(self, stats_service):
        """Test cache management functionality"""
        # Test cache size management - add more than max_cache_size
        for i in range(1200):  # More than the max_cache_size of 1000
            cache_key = f"test_key_{i}"
            await stats_service._set_cached_stats(cache_key, [{"data": i}])
        
        # Should have reduced cache size after cleanup
        assert len(stats_service._cache) <= 1000  # Should not exceed max size
        
        # Test cache cleanup
        removed_count = await stats_service.cleanup_expired_cache()
        assert isinstance(removed_count, int)
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, stats_service):
        """Test cache invalidation"""
        # Add some cached data
        await stats_service._set_cached_stats("athlete_stats_athlete123_123_10_0", [{"data": "test"}])
        
        # Invalidate cache
        await stats_service._invalidate_stats_cache("athlete123")
        
        # Cache should be empty
        assert len(stats_service._cache) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling_database_error(self, stats_service):
        """Test database error handling"""
        stats_service.stats_db.get_by_id = AsyncMock(side_effect=Exception("Database connection failed"))
        
        with pytest.raises(DatabaseError, match="Failed to retrieve stats record"):
            await stats_service.get_stats_by_id("stats123")
    
    @pytest.mark.asyncio
    async def test_parallel_processing_summary(self, stats_service, mock_stats_data):
        """Test parallel processing in stats summary"""
        mock_records = [mock_stats_data]
        mock_categories = [{"id": "soccer", "name": "Soccer/Football"}]
        
        stats_service.stats_db.count = AsyncMock(return_value=1)
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        stats_service.categories_db.query = AsyncMock(return_value=mock_categories)
        
        # This should use parallel processing internally
        result = await stats_service.get_athlete_stats_summary("athlete123")
        
        assert "total_seasons" in result
        assert "sports_played" in result
        assert "achievements_count" in result 
    
    @pytest.mark.asyncio
    async def test_bulk_create_stats_validation_error(self, stats_service, mock_stats_data):
        """Test bulk create stats with validation error"""
        # Create valid stats data that matches the mock schema
        valid_stats_data = mock_stats_data.copy()
        valid_stats_data["stats"] = {"games_played": 25}  # Only valid field according to mock schema
        
        # Create invalid stats data with only invalid field
        invalid_stats_data = mock_stats_data.copy()
        invalid_stats_data["stats"] = {"invalid_field": 10}  # Only invalid field
        
        stats_list = [valid_stats_data, invalid_stats_data]
        
        # Mock sport category for validation - only allow games_played
        mock_sport_category = {
            "id": "soccer",
            "is_active": True,
            "stats_fields": [
                {"key": "games_played", "type": "integer", "required": True}
            ]
        }
        stats_service.categories_db.get_by_id = AsyncMock(return_value=mock_sport_category)
        
        with pytest.raises(DatabaseError, match="Validation error for record 1"):
            await stats_service.bulk_create_stats(stats_list)
    
    @pytest.mark.asyncio
    async def test_get_athlete_stats_with_filters(self, stats_service, mock_stats_data):
        """Test getting athlete stats with additional filters"""
        mock_records = [mock_stats_data]
        filters = {"season": "2023-2024", "sport_category_id": "soccer"}
        
        stats_service.stats_db.count = AsyncMock(return_value=1)
        stats_service.stats_db.query = AsyncMock(return_value=mock_records)
        
        result = await stats_service.get_athlete_stats(
            athlete_id="athlete123",
            filters=filters,
            limit=10,
            offset=0
        )
        
        assert result["count"] == 1
        assert len(result["results"]) == 1
        assert result["limit"] == 10
        assert result["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_update_stats_with_sport_category_change(self, stats_service, mock_stats_data):
        """Test updating stats with sport category change"""
        # Mock existing record
        existing_record = {**mock_stats_data, "sport_category_id": "soccer"}
        
        # Mock new sport category
        new_sport_category = {
            "id": "basketball",
            "is_active": True,
            "stats_fields": [
                {"key": "points_per_game", "type": "float", "required": True}
            ]
        }
        
        stats_service.stats_db.get_by_id = AsyncMock(side_effect=[
            existing_record,  # existing record
            {**existing_record, "sport_category_id": "basketball"}  # updated record
        ])
        stats_service.categories_db.get_by_id = AsyncMock(return_value=new_sport_category)
        stats_service.stats_db.update = AsyncMock()
        
        update_data = {
            "sport_category_id": "basketball",
            "stats": {"points_per_game": 25.5}
        }
        
        result = await stats_service.update_stats("stats123", update_data)
        
        assert result["sport_category_id"] == "basketball"
        stats_service.stats_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(self, stats_service):
        """Test cache cleanup functionality"""
        # Add some cached data
        await stats_service._set_cached_stats("key1", [{"data": "test1"}])
        await stats_service._set_cached_stats("key2", [{"data": "test2"}])
        
        # Manually expire cache entries
        stats_service._cache["key1"]["cached_at"] = datetime.now() - timedelta(hours=1)
        
        # Clean up expired entries
        removed_count = await stats_service.cleanup_expired_cache()
        
        assert removed_count == 1
        assert "key1" not in stats_service._cache
        assert "key2" in stats_service._cache 