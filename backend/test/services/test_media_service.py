"""
Tests for refactored media services
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.media_service import MediaService
from app.services.media_upload_service import MediaUploadService
from app.services.media_query_service import MediaQueryService
from app.aiAgents.media_analysis_agent import MediaAnalysisAgent
from app.aiAgents.media_recommendation_agent import MediaRecommendationAgent
from app.models.media import MediaCreate, MediaUpdate
from app.models.media_responses import MediaResponse, MediaListResponse, BulkUploadResponse, AIAnalysisResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError, DatabaseError
from firebase_admin.firestore import FieldFilter


class TestMediaUploadService:
    """Test MediaUploadService"""
    
    @pytest.fixture
    def upload_service(self):
        return MediaUploadService()
    
    @pytest.fixture
    def mock_media_data(self):
        return MediaCreate(
            type="video",
            description="Test video"
        )
    
    @pytest.mark.asyncio
    async def test_upload_media_success(self, upload_service, mock_media_data):
        """Test successful media upload"""
        # Mock dependencies
        upload_service.database_service.create = AsyncMock(return_value="media_123")
        upload_service.database_service.get_by_id = AsyncMock(return_value={
            "id": "media_123",
            "athlete_id": "athlete_123",
            "type": "video",
            "url": "https://example.com/video.mp4",
            "thumbnail_url": None,
            "description": "Test video",
            "moderation_status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
            "ai_analysis": {"status": "pending"}
        })
        upload_service.analysis_agent._create_background_task = AsyncMock()
        
        # Test upload
        result = await upload_service.upload_media(
            "athlete_123", 
            mock_media_data, 
            "https://example.com/video.mp4"
        )
        
        assert isinstance(result, MediaResponse)
        assert result.id == "media_123"
        assert result.athlete_id == "athlete_123"
        assert result.type == "video"
    
    @pytest.mark.asyncio
    async def test_upload_media_validation_error(self, upload_service, mock_media_data):
        """Test media upload with validation error"""
        with pytest.raises(ValidationError, match="Invalid media type"):
            await upload_service.upload_media(
                "athlete_123",
                MediaCreate(type="invalid_type", description="Test"),
                "https://example.com/video.mp4"
            )
    
    @pytest.mark.asyncio
    async def test_bulk_upload_media_success(self, upload_service):
        """Test successful bulk media upload"""
        media_list = [
            {
                "metadata": {"type": "video", "description": "Video 1"},
                "file_url": "https://example.com/video1.mp4"
            },
            {
                "metadata": {"type": "image", "description": "Image 1"},
                "file_url": "https://example.com/image1.jpg"
            }
        ]
        
        # Mock dependencies
        upload_service.database_service.create = AsyncMock(side_effect=["media_1", "media_2"])
        upload_service.database_service.get_by_id = AsyncMock(return_value={
            "id": "media_1",
            "athlete_id": "athlete_123",
            "type": "video",
            "url": "https://example.com/video1.mp4",
            "moderation_status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
            "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
        })
        upload_service.analysis_agent._create_background_task = AsyncMock()
        
        result = await upload_service.bulk_upload_media("athlete_123", media_list)
        
        assert isinstance(result, BulkUploadResponse)
        assert result.uploaded_count == 2
        assert result.failed_count == 0
        assert len(result.media_ids) == 2


class TestMediaQueryService:
    """Test MediaQueryService"""
    
    @pytest.fixture
    def query_service(self):
        return MediaQueryService()
    
    @pytest.mark.asyncio
    async def test_get_media_by_id_success(self, query_service):
        """Test successful media retrieval by ID"""
        mock_media_doc = {
            "id": "media_123",
            "athlete_id": "athlete_123",
            "type": "video",
            "url": "https://example.com/video.mp4",
            "thumbnail_url": None,
            "description": "Test video",
            "moderation_status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
            "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
        }
        
        query_service.database_service.get_by_id = AsyncMock(return_value=mock_media_doc)
        
        result = await query_service.get_media_by_id("media_123")
        
        assert isinstance(result, MediaResponse)
        assert result.id == "media_123"
        assert result.athlete_id == "athlete_123"
    
    @pytest.mark.asyncio
    async def test_get_media_by_id_not_found(self, query_service):
        """Test media retrieval with non-existent ID"""
        query_service.database_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Media not found"):
            await query_service.get_media_by_id("non_existent")
    
    @pytest.mark.asyncio
    async def test_get_athlete_media_success(self, query_service):
        """Test successful athlete media retrieval"""
        mock_media_docs = [
            {
                "id": "media_1",
                "athlete_id": "athlete_123",
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            },
            {
                "id": "media_2",
                "athlete_id": "athlete_123",
                "type": "image",
                "url": "https://example.com/image1.jpg",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            }
        ]
        
        query_service.database_service.query = AsyncMock(return_value=mock_media_docs)
        query_service.database_service.count = AsyncMock(return_value=2)
        
        result = await query_service.get_athlete_media("athlete_123", limit=10, offset=0)
        
        assert isinstance(result, MediaListResponse)
        assert len(result.media) == 2
        assert result.total_count == 2
        assert result.limit == 10
        assert result.offset == 0
    
    # New tests for improvements
    
    def test_configuration_constants(self, query_service):
        """Test that configuration constants are properly set"""
        assert hasattr(query_service, 'DEFAULT_MEDIA_LIMIT')
        assert hasattr(query_service, 'MAX_MEDIA_LIMIT')
        assert hasattr(query_service, 'DEFAULT_SEARCH_LIMIT')
        assert hasattr(query_service, 'MAX_SEARCH_LIMIT')
        
        assert isinstance(query_service.DEFAULT_MEDIA_LIMIT, int)
        assert isinstance(query_service.MAX_MEDIA_LIMIT, int)
        assert isinstance(query_service.DEFAULT_SEARCH_LIMIT, int)
        assert isinstance(query_service.MAX_SEARCH_LIMIT, int)
        
        assert query_service.DEFAULT_MEDIA_LIMIT > 0
        assert query_service.MAX_MEDIA_LIMIT > query_service.DEFAULT_MEDIA_LIMIT
        assert query_service.DEFAULT_SEARCH_LIMIT > 0
        assert query_service.MAX_SEARCH_LIMIT > query_service.DEFAULT_SEARCH_LIMIT
    
    def test_configuration_validation(self, query_service):
        """Test that configuration validation works correctly"""
        # Test that validation passes with valid config
        try:
            query_service._validate_config()
        except ValueError:
            pytest.fail("Configuration validation should pass with valid config")
    
    @pytest.mark.asyncio
    async def test_default_limit_behavior(self, query_service):
        """Test that default limits are used when None is passed"""
        mock_media_docs = [
            {
                "id": "media_1",
                "athlete_id": "athlete_123",
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            }
        ]
        
        query_service.database_service.query = AsyncMock(return_value=mock_media_docs)
        query_service.database_service.count = AsyncMock(return_value=1)
        
        # Call without specifying limit
        result = await query_service.get_athlete_media("athlete_123")
        
        # Should use default limit
        assert result.limit == query_service.DEFAULT_MEDIA_LIMIT
        query_service.database_service.query.assert_called_once_with(
            [FieldFilter("athlete_id", "==", "athlete_123")], 
            query_service.DEFAULT_MEDIA_LIMIT, 
            0
        )
    
    @pytest.mark.asyncio
    async def test_input_validation_limits(self, query_service):
        """Test input validation for limit values"""
        # Test invalid limit values
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.get_athlete_media("test_athlete", limit=0, offset=0)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.get_athlete_media("test_athlete", limit=query_service.MAX_MEDIA_LIMIT + 1, offset=0)
        
        # Test invalid offset
        with pytest.raises(ValidationError, match="Offset must be non-negative"):
            await query_service.get_athlete_media("test_athlete", limit=10, offset=-1)
    
    @pytest.mark.asyncio
    async def test_input_validation_search_limits(self, query_service):
        """Test input validation for search limit values"""
        # Test invalid search limit values
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.search_media("test query", limit=0)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.search_media("test query", limit=query_service.MAX_SEARCH_LIMIT + 1)
    
    @pytest.mark.asyncio
    async def test_input_validation_media_type_limits(self, query_service):
        """Test input validation for media type limit values"""
        # Test invalid media type limit values
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.get_media_by_type("video", limit=0)
        
        with pytest.raises(ValidationError, match="Limit must be between 1 and"):
            await query_service.get_media_by_type("video", limit=query_service.MAX_SEARCH_LIMIT + 1)
    
    @pytest.mark.asyncio
    async def test_helper_method_convert_multiple_docs(self, query_service):
        """Test the helper method for converting multiple media documents"""
        mock_media_docs = [
            {
                "id": "media_1",
                "athlete_id": "athlete_123",
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            },
            {
                "id": "media_2",
                "athlete_id": "athlete_123",
                "type": "image",
                "url": "https://example.com/image1.jpg",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            }
        ]
        
        responses = await query_service._convert_multiple_media_docs(mock_media_docs)
        
        assert len(responses) == 2
        assert isinstance(responses[0], MediaResponse)
        assert isinstance(responses[1], MediaResponse)
        assert responses[0].id == "media_1"
        assert responses[1].id == "media_2"
    
    @pytest.mark.asyncio
    async def test_helper_method_convert_multiple_docs_with_errors(self, query_service):
        """Test helper method with malformed data (should skip invalid items)"""
        mock_media_docs = [
            {
                "id": "media_1",
                "athlete_id": "athlete_123",
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            },
            {
                # Missing required fields - should be skipped
                "id": "media_2",
                "type": "image"
            },
            {
                "id": "media_3",
                "athlete_id": "athlete_123",
                "type": "video",
                "url": "https://example.com/video3.mp4",
                "moderation_status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "ai_analysis": {"status": "pending", "retry_count": 0, "max_retries": 5}
            }
        ]
        
        responses = await query_service._convert_multiple_media_docs(mock_media_docs)
        
        # Should only convert valid items
        assert len(responses) == 2
        assert responses[0].id == "media_1"
        assert responses[1].id == "media_3"
    
    def test_helper_method_filter_media_by_query(self, query_service):
        """Test the helper method for filtering media by query"""
        mock_media_docs = [
            {
                "id": "media_1",
                "description": "Basketball highlights",
                "type": "video",
                "sport_category": "basketball"
            },
            {
                "id": "media_2",
                "description": "Soccer match",
                "type": "video",
                "sport_category": "soccer"
            },
            {
                "id": "media_3",
                "description": "Tennis serve",
                "type": "video",
                "sport_category": "tennis"
            }
        ]
        
        # Test filtering by sport category
        filtered = query_service._filter_media_by_query(mock_media_docs, "basketball", 10)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "media_1"
        
        # Test filtering by description
        filtered = query_service._filter_media_by_query(mock_media_docs, "soccer", 10)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "media_2"
        
        # Test filtering with limit
        filtered = query_service._filter_media_by_query(mock_media_docs, "video", 2)
        assert len(filtered) == 2
    
    def test_service_status(self, query_service):
        """Test service status retrieval"""
        status = query_service.get_service_status()
        
        assert "service" in status
        assert "status" in status
        assert "database_service" in status
        assert "config" in status
        
        assert status["service"] == "MediaQueryService"
        assert status["status"] == "active"
        assert status["database_service"] == "active"
        
        config = status["config"]
        assert "default_media_limit" in config
        assert "max_media_limit" in config
        assert "default_search_limit" in config
        assert "max_search_limit" in config
        assert "supported_types" in config
    
    @pytest.mark.asyncio
    async def test_improved_error_handling_consistency(self, query_service):
        """Test that error handling is consistent across methods"""
        # Mock database error
        query_service.database_service.get_by_id = AsyncMock(side_effect=Exception("Database connection failed"))
        
        # Should raise DatabaseError instead of returning None
        with pytest.raises(DatabaseError, match="Failed to get media"):
            await query_service.get_media_by_id("test_media_id")
    
    @pytest.mark.asyncio
    async def test_search_media_default_limit(self, query_service):
        """Test that search media uses default limit when None is passed"""
        mock_media_docs = []
        query_service.database_service.query = AsyncMock(return_value=mock_media_docs)
        
        # Call without specifying limit
        result = await query_service.search_media("test query")
        
        # Should use default search limit
        assert result.limit == query_service.DEFAULT_SEARCH_LIMIT
    
    @pytest.mark.asyncio
    async def test_get_media_by_type_default_limit(self, query_service):
        """Test that get_media_by_type uses default limit when None is passed"""
        mock_media_docs = []
        query_service.database_service.query = AsyncMock(return_value=mock_media_docs)
        query_service.database_service.count = AsyncMock(return_value=0)
        
        # Call without specifying limit
        result = await query_service.get_media_by_type("video")
        
        # Should use default search limit
        assert result.limit == query_service.DEFAULT_SEARCH_LIMIT 