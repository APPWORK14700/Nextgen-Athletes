"""
Tests for SearchService
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.search_service import SearchService
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError


class TestSearchService:
    """Test cases for SearchService"""
    
    @pytest.fixture
    def search_service(self):
        """Create a SearchService instance with mocked database service"""
        service = SearchService.__new__(SearchService)
        
        # Mock the database service
        service.db = Mock()
        
        # Initialize configuration
        service.max_searches_per_user = 100
        service.default_suggestion_limit = 5
        
        return service
    
    @pytest.fixture
    def mock_search_data(self):
        """Mock search data"""
        return {
            "id": "search123",
            "user_id": "user123",
            "search_type": "athletes",
            "query": "soccer players",
            "filters": {"sport_category_id": "soccer", "age_range": {"min": 18, "max": 25}},
            "created_at": "2024-01-15T10:00:00"
        }
    
    @pytest.mark.asyncio
    async def test_save_search_success(self, search_service, mock_search_data):
        """Test successful search saving"""
        search_service.db.create = AsyncMock(return_value="search123")
        search_service.db.get_by_id = AsyncMock(return_value=mock_search_data)
        search_service.db.query = AsyncMock(return_value=[])  # No old searches to clean up
        
        result = await search_service.save_search(
            user_id="user123",
            search_type="athletes",
            query="soccer players",
            filters={"sport_category_id": "soccer"}
        )
        
        assert result["id"] == "search123"
        assert result["user_id"] == "user123"
        assert result["search_type"] == "athletes"
        search_service.db.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_search_invalid_type(self, search_service):
        """Test saving search with invalid search type"""
        with pytest.raises(ValidationError, match="Invalid search type"):
            await search_service.save_search(
                user_id="user123",
                search_type="invalid_type",
                query="test query",
                filters={}
            )
    
    @pytest.mark.asyncio
    async def test_save_search_empty_query(self, search_service):
        """Test saving search with empty query"""
        with pytest.raises(ValidationError, match="Search query cannot be empty"):
            await search_service.save_search(
                user_id="user123",
                search_type="athletes",
                query="",
                filters={}
            )
    
    @pytest.mark.asyncio
    async def test_get_user_search_history_success(self, search_service, mock_search_data):
        """Test getting user search history successfully"""
        mock_searches = [mock_search_data]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.count = AsyncMock(return_value=1)
        
        result = await search_service.get_user_search_history(
            user_id="user123",
            page=1,
            limit=20
        )
        
        assert result["searches"] == mock_searches
        assert result["total"] == 1
        assert result["page"] == 1
        assert result["limit"] == 20
        assert result["has_next"] is False
        assert result["has_previous"] is False
    
    @pytest.mark.asyncio
    async def test_get_user_search_history_with_filter(self, search_service, mock_search_data):
        """Test getting user search history with search type filter"""
        mock_searches = [mock_search_data]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.count = AsyncMock(return_value=1)
        
        result = await search_service.get_user_search_history(
            user_id="user123",
            search_type="athletes",
            page=1,
            limit=20
        )
        
        assert result["searches"] == mock_searches
        assert result["total"] == 1
    
    @pytest.mark.asyncio
    async def test_get_user_search_history_invalid_type(self, search_service):
        """Test getting search history with invalid search type"""
        with pytest.raises(ValidationError, match="Invalid search type"):
            await search_service.get_user_search_history(
                user_id="user123",
                search_type="invalid_type"
            )
    
    @pytest.mark.asyncio
    async def test_delete_search_history_item_success(self, search_service, mock_search_data):
        """Test successful deletion of search history item"""
        search_service.db.get_by_id = AsyncMock(return_value=mock_search_data)
        search_service.db.delete = AsyncMock()
        
        await search_service.delete_search_history_item("search123", "user123")
        
        search_service.db.delete.assert_called_once_with("search123")
    
    @pytest.mark.asyncio
    async def test_delete_search_history_item_not_found(self, search_service):
        """Test deleting non-existent search history item"""
        search_service.db.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Search history item not found"):
            await search_service.delete_search_history_item("invalid_id", "user123")
    
    @pytest.mark.asyncio
    async def test_delete_search_history_item_unauthorized(self, search_service, mock_search_data):
        """Test deleting search history item with wrong user"""
        search_service.db.get_by_id = AsyncMock(return_value=mock_search_data)
        
        with pytest.raises(ValidationError, match="You can only delete your own search history"):
            await search_service.delete_search_history_item("search123", "different_user")
    
    @pytest.mark.asyncio
    async def test_clear_user_search_history_success(self, search_service, mock_search_data):
        """Test successful clearing of user search history"""
        mock_searches = [mock_search_data]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.batch_delete = AsyncMock()
        
        await search_service.clear_user_search_history("user123")
        
        search_service.db.batch_delete.assert_called_once_with(["search123"])
    
    @pytest.mark.asyncio
    async def test_get_popular_searches_success(self, search_service):
        """Test getting popular searches successfully"""
        mock_searches = [
            {"query": "soccer players", "created_at": "2024-01-15T10:00:00"},
            {"query": "soccer players", "created_at": "2024-01-15T11:00:00"},
            {"query": "basketball players", "created_at": "2024-01-15T12:00:00"}
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        
        result = await search_service.get_popular_searches(
            search_type="athletes",
            days=30,
            limit=10
        )
        
        assert len(result) == 2
        assert result[0]["term"] == "soccer players"
        assert result[0]["count"] == 2
        assert result[1]["term"] == "basketball players"
        assert result[1]["count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_popular_searches_invalid_type(self, search_service):
        """Test getting popular searches with invalid search type"""
        with pytest.raises(ValidationError, match="Invalid search type"):
            await search_service.get_popular_searches(search_type="invalid_type")
    
    @pytest.mark.asyncio
    async def test_get_search_suggestions_success(self, search_service):
        """Test getting search suggestions successfully"""
        mock_user_searches = [
            {"query": "soccer players california", "created_at": "2024-01-15T10:00:00"},
            {"query": "soccer players texas", "created_at": "2024-01-15T11:00:00"}
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_user_searches)
        
        result = await search_service.get_search_suggestions(
            user_id="user123",
            search_type="athletes",
            partial_query="soccer",
            limit=5
        )
        
        assert len(result) == 2
        assert "soccer players california" in result
        assert "soccer players texas" in result
    
    @pytest.mark.asyncio
    async def test_get_search_suggestions_invalid_type(self, search_service):
        """Test getting search suggestions with invalid search type"""
        with pytest.raises(ValidationError, match="Invalid search type"):
            await search_service.get_search_suggestions(
                user_id="user123",
                search_type="invalid_type",
                partial_query="test"
            )
    
    @pytest.mark.asyncio
    async def test_get_search_analytics_success(self, search_service):
        """Test getting search analytics successfully"""
        mock_searches = [
            {
                "search_type": "athletes",
                "query": "soccer players",
                "created_at": "2024-01-15T10:00:00"
            },
            {
                "search_type": "athletes",
                "query": "basketball players",
                "created_at": "2024-01-15T11:00:00"
            },
            {
                "search_type": "opportunities",
                "query": "scholarships",
                "created_at": "2024-01-15T12:00:00"
            }
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        
        result = await search_service.get_search_analytics("user123")
        
        assert result["total_searches"] == 3
        assert result["searches_by_type"]["athletes"] == 2
        assert result["searches_by_type"]["opportunities"] == 1
        assert len(result["most_common_terms"]) == 3
        assert len(result["recent_searches"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_search_analytics_empty(self, search_service):
        """Test getting search analytics for user with no searches"""
        search_service.db.query = AsyncMock(return_value=[])
        
        result = await search_service.get_search_analytics("user123")
        
        assert result["total_searches"] == 0
        assert result["searches_by_type"] == {}
        assert result["most_common_terms"] == []
        assert result["recent_searches"] == []
    
    @pytest.mark.asyncio
    async def test_get_search_trends_success(self, search_service):
        """Test getting search trends successfully"""
        mock_searches = [
            {
                "search_type": "athletes",
                "query": "soccer players",
                "created_at": "2024-01-15T10:00:00"
            },
            {
                "search_type": "athletes",
                "query": "soccer players",
                "created_at": "2024-01-15T11:00:00"
            }
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        
        result = await search_service.get_search_trends(
            search_type="athletes",
            days=30
        )
        
        assert result["total_searches"] == 2
        assert result["search_type_distribution"]["athletes"] == 2
        assert len(result["top_queries"]) == 1
        assert result["top_queries"][0]["query"] == "soccer players"
        assert result["top_queries"][0]["count"] == 2
    
    @pytest.mark.asyncio
    async def test_get_search_trends_invalid_type(self, search_service):
        """Test getting search trends with invalid search type"""
        with pytest.raises(ValidationError, match="Invalid search type"):
            await search_service.get_search_trends(search_type="invalid_type")
    
    @pytest.mark.asyncio
    async def test_cleanup_old_searches(self, search_service):
        """Test cleanup of old searches"""
        # Mock more searches than the limit
        mock_searches = [
            {"id": f"search{i}", "created_at": f"2024-01-{i:02d}T10:00:00"}
            for i in range(1, 105)  # 104 searches, over the limit of 100
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.batch_delete = AsyncMock()
        
        await search_service._cleanup_old_searches("user123")
        
        # Should delete 4 oldest searches (104 - 100 = 4)
        expected_deleted_ids = [f"search{i}" for i in range(1, 5)]
        search_service.db.batch_delete.assert_called_once_with(expected_deleted_ids)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_searches_no_cleanup_needed(self, search_service):
        """Test cleanup when no cleanup is needed"""
        mock_searches = [
            {"id": f"search{i}", "created_at": f"2024-01-{i:02d}T10:00:00"}
            for i in range(1, 51)  # 50 searches, under the limit of 100
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.batch_delete = AsyncMock()
        
        await search_service._cleanup_old_searches("user123")
        
        # Should not call batch_delete
        search_service.db.batch_delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_error_handling_database_error(self, search_service):
        """Test database error handling"""
        search_service.db.create = AsyncMock(side_effect=Exception("Database connection failed"))
        
        with pytest.raises(DatabaseError, match="Failed to save search"):
            await search_service.save_search(
                user_id="user123",
                search_type="athletes",
                query="test query",
                filters={}
            )
    
    @pytest.mark.asyncio
    async def test_pagination_with_has_next(self, search_service, mock_search_data):
        """Test pagination with has_next flag"""
        mock_searches = [mock_search_data]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.count = AsyncMock(return_value=25)  # More than page size
        
        result = await search_service.get_user_search_history(
            user_id="user123",
            page=1,
            limit=20
        )
        
        assert result["has_next"] is True
        assert result["has_previous"] is False
        assert result["total"] == 25
    
    @pytest.mark.asyncio
    async def test_pagination_with_has_previous(self, search_service, mock_search_data):
        """Test pagination with has_previous flag"""
        mock_searches = [mock_search_data]
        
        search_service.db.query = AsyncMock(return_value=mock_searches)
        search_service.db.count = AsyncMock(return_value=25)
        
        result = await search_service.get_user_search_history(
            user_id="user123",
            page=2,
            limit=20
        )
        
        assert result["has_next"] is False
        assert result["has_previous"] is True
        assert result["page"] == 2
    
    @pytest.mark.asyncio
    async def test_search_suggestions_with_popular_fallback(self, search_service):
        """Test search suggestions with popular searches fallback"""
        # Mock user searches that don't match
        mock_user_searches = [
            {"query": "basketball players", "created_at": "2024-01-15T10:00:00"}
        ]
        
        # Mock popular searches that do match
        mock_popular_searches = [
            {"term": "soccer players california", "count": 5},
            {"term": "soccer players texas", "count": 3}
        ]
        
        search_service.db.query = AsyncMock(return_value=mock_user_searches)
        
        # Mock the get_popular_searches method
        with patch.object(search_service, 'get_popular_searches', AsyncMock(return_value=mock_popular_searches)):
            result = await search_service.get_search_suggestions(
                user_id="user123",
                search_type="athletes",
                partial_query="soccer",
                limit=5
            )
        
        assert len(result) == 2
        assert "soccer players california" in result
        assert "soccer players texas" in result 