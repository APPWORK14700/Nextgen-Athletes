import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.services.media_service import MediaService
from app.models.media import MediaCreate, MediaUpdate
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError


class TestMediaService:
    """Test cases for MediaService"""
    
    @pytest.fixture
    def media_service(self):
        service = MediaService.__new__(MediaService)
        service.media_service = AsyncMock()
        service.ai_service = AsyncMock()
        service.max_uploads_per_hour = 20
        service.max_file_size_mb = 100
        service.supported_types = ["video", "image", "reel"]
        service.supported_formats = {
            "video": ["mp4", "mov", "avi"],
            "image": ["jpg", "jpeg", "png", "gif"],
            "reel": ["mp4", "mov"]
        }
        return service
    
    @pytest.fixture
    def mock_media_data(self):
        return {
            "id": "media123",
            "athlete_id": "athlete123",
            "type": "video",
            "url": "https://example.com/video.mp4",
            "thumbnail_url": "https://example.com/thumbnail.jpg",
            "description": "Game highlights",
            "moderation_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ai_analysis": {
                "status": "pending",
                "rating": None,
                "summary": None,
                "detailed_analysis": None,
                "sport_specific_metrics": None,
                "confidence_score": None,
                "analysis_started_at": None,
                "analysis_completed_at": None,
                "retry_count": 0,
                "max_retries": 5,
                "next_retry_at": None,
                "error_message": None
            }
        }
    
    @pytest.fixture
    def mock_media_create(self):
        return MediaCreate(
            type="video",
            description="Game highlights"
        )
    
    @pytest.fixture
    def mock_media_update(self):
        return MediaUpdate(
            description="Updated description"
        )
    
    # Test upload_media
    @pytest.mark.asyncio
    async def test_upload_media_success(self, media_service, mock_media_create, mock_media_data):
        """Test successful media upload"""
        media_service.media_service.create = AsyncMock(return_value="media123")
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.count = AsyncMock(return_value=5)  # Rate limit check
        
        result = await media_service.upload_media("athlete123", mock_media_create, "https://example.com/video.mp4", "https://example.com/thumbnail.jpg")
        
        assert result is not None
        media_service.media_service.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upload_media_missing_athlete_id(self, media_service, mock_media_create):
        """Test media upload with missing athlete ID"""
        with pytest.raises(ValidationError, match="Athlete ID is required"):
            await media_service.upload_media("", mock_media_create, "https://example.com/video.mp4")
    
    @pytest.mark.asyncio
    async def test_upload_media_missing_file_url(self, media_service, mock_media_create):
        """Test media upload with missing file URL"""
        with pytest.raises(ValidationError, match="File URL is required"):
            await media_service.upload_media("athlete123", mock_media_create, "")
    
    @pytest.mark.asyncio
    async def test_upload_media_invalid_url(self, media_service, mock_media_create):
        """Test media upload with invalid URL"""
        with pytest.raises(ValidationError, match="Invalid file URL format"):
            await media_service.upload_media("athlete123", mock_media_create, "invalid-url")
    
    @pytest.mark.asyncio
    async def test_upload_media_rate_limit_exceeded(self, media_service, mock_media_create):
        """Test media upload when rate limit is exceeded"""
        media_service.media_service.count = AsyncMock(return_value=20)  # Rate limit exceeded
        
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            await media_service.upload_media("athlete123", mock_media_create, "https://example.com/video.mp4")
    
    # Test get_media_by_id
    @pytest.mark.asyncio
    async def test_get_media_by_id_success(self, media_service, mock_media_data):
        """Test successful media retrieval by ID"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        result = await media_service.get_media_by_id("media123")
        
        assert result == mock_media_data
        media_service.media_service.get_by_id.assert_called_once_with("media123")
    
    @pytest.mark.asyncio
    async def test_get_media_by_id_missing_id(self, media_service):
        """Test media retrieval with missing ID"""
        with pytest.raises(ValidationError, match="Media ID is required"):
            await media_service.get_media_by_id("")
    
    @pytest.mark.asyncio
    async def test_get_media_by_id_not_found(self, media_service):
        """Test media retrieval when media doesn't exist"""
        media_service.media_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Media not found"):
            await media_service.get_media_by_id("media123")
    
    # Test get_athlete_media
    @pytest.mark.asyncio
    async def test_get_athlete_media_success(self, media_service, mock_media_data):
        """Test successful athlete media retrieval"""
        mock_media_list = [mock_media_data, mock_media_data]
        media_service.media_service.query = AsyncMock(return_value=mock_media_list)
        
        result = await media_service.get_athlete_media("athlete123", 10, 0)
        
        assert len(result) == 2
        media_service.media_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_athlete_media_missing_athlete_id(self, media_service):
        """Test athlete media retrieval with missing athlete ID"""
        with pytest.raises(ValidationError, match="Athlete ID is required"):
            await media_service.get_athlete_media("", 10, 0)
    
    @pytest.mark.asyncio
    async def test_get_athlete_media_invalid_limit(self, media_service):
        """Test athlete media retrieval with invalid limit"""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 1000"):
            await media_service.get_athlete_media("athlete123", 0, 0)
    
    # Test update_media
    @pytest.mark.asyncio
    async def test_update_media_success(self, media_service, mock_media_update, mock_media_data):
        """Test successful media update"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.update = AsyncMock()
        
        result = await media_service.update_media("media123", mock_media_update, "athlete123")
        
        assert result == mock_media_data
        media_service.media_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_media_unauthorized(self, media_service, mock_media_update, mock_media_data):
        """Test media update with wrong athlete"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await media_service.update_media("media123", mock_media_update, "wrong_athlete")
    
    @pytest.mark.asyncio
    async def test_update_media_missing_media_id(self, media_service, mock_media_update):
        """Test media update with missing media ID"""
        with pytest.raises(ValidationError, match="Media ID is required"):
            await media_service.update_media("", mock_media_update, "athlete123")
    
    # Test delete_media
    @pytest.mark.asyncio
    async def test_delete_media_success(self, media_service, mock_media_data):
        """Test successful media deletion"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.delete = AsyncMock()
        
        result = await media_service.delete_media("media123", "athlete123")
        
        assert result is True
        media_service.media_service.delete.assert_called_once_with("media123")
    
    @pytest.mark.asyncio
    async def test_delete_media_unauthorized(self, media_service, mock_media_data):
        """Test media deletion with wrong athlete"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await media_service.delete_media("media123", "wrong_athlete")
    
    # Test get_media_status
    @pytest.mark.asyncio
    async def test_get_media_status_success(self, media_service, mock_media_data):
        """Test successful media status retrieval"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        result = await media_service.get_media_status("media123", "athlete123")
        
        assert result["media_id"] == "media123"
        assert "ai_analysis" in result
    
    @pytest.mark.asyncio
    async def test_get_media_status_unauthorized(self, media_service, mock_media_data):
        """Test media status retrieval with wrong athlete"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await media_service.get_media_status("media123", "wrong_athlete")
    
    # Test retry_ai_analysis
    @pytest.mark.asyncio
    async def test_retry_ai_analysis_success(self, media_service, mock_media_data):
        """Test successful AI analysis retry"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.update = AsyncMock()
        
        result = await media_service.retry_ai_analysis("media123", "athlete123")
        
        assert result is True
        media_service.media_service.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retry_ai_analysis_unauthorized(self, media_service, mock_media_data):
        """Test AI analysis retry with wrong athlete"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await media_service.retry_ai_analysis("media123", "wrong_athlete")
    
    @pytest.mark.asyncio
    async def test_retry_ai_analysis_max_retries(self, media_service, mock_media_data):
        """Test AI analysis retry when max retries reached"""
        mock_data = mock_media_data.copy()
        mock_data["ai_analysis"]["retry_count"] = 5
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_data)
        
        with pytest.raises(ValidationError, match="Maximum retry attempts reached"):
            await media_service.retry_ai_analysis("media123", "athlete123")
    
    # Test get_recommended_reels
    @pytest.mark.asyncio
    async def test_get_recommended_reels_success(self, media_service, mock_media_data):
        """Test successful recommended reels retrieval"""
        mock_reels = [mock_media_data, mock_media_data]
        media_service.media_service.query = AsyncMock(return_value=mock_reels)
        
        result = await media_service.get_recommended_reels("scout123", 10)
        
        assert len(result) <= 10
        media_service.media_service.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_recommended_reels_missing_scout_id(self, media_service):
        """Test recommended reels retrieval with missing scout ID"""
        with pytest.raises(ValidationError, match="Scout ID is required"):
            await media_service.get_recommended_reels("", 10)
    
    @pytest.mark.asyncio
    async def test_get_recommended_reels_invalid_limit(self, media_service):
        """Test recommended reels retrieval with invalid limit"""
        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            await media_service.get_recommended_reels("scout123", 0)
    
    # Test bulk_upload_media
    @pytest.mark.asyncio
    async def test_bulk_upload_media_success(self, media_service, mock_media_data):
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
        
        media_service.media_service.create = AsyncMock(side_effect=["media1", "media2"])
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.count = AsyncMock(return_value=5)
        
        result = await media_service.bulk_upload_media("athlete123", media_list)
        
        assert result["uploaded_count"] == 2
        assert result["failed_count"] == 0
        assert len(result["media_ids"]) == 2
    
    @pytest.mark.asyncio
    async def test_bulk_upload_media_missing_athlete_id(self, media_service):
        """Test bulk upload with missing athlete ID"""
        media_list = [{"metadata": {"type": "video"}, "file_url": "https://example.com/video.mp4"}]
        
        with pytest.raises(ValidationError, match="Athlete ID is required"):
            await media_service.bulk_upload_media("", media_list)
    
    @pytest.mark.asyncio
    async def test_bulk_upload_media_too_many_files(self, media_service):
        """Test bulk upload with too many files"""
        media_list = [{"metadata": {"type": "video"}, "file_url": "https://example.com/video.mp4"}] * 11
        
        with pytest.raises(ValidationError, match="Maximum 10 files per bulk upload"):
            await media_service.bulk_upload_media("athlete123", media_list)
    
    # Test bulk_delete_media
    @pytest.mark.asyncio
    async def test_bulk_delete_media_success(self, media_service, mock_media_data):
        """Test successful bulk media deletion"""
        media_ids = ["media1", "media2"]
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.media_service.batch_delete = AsyncMock()
        
        result = await media_service.bulk_delete_media(media_ids, "athlete123")
        
        assert result is True
        media_service.media_service.batch_delete.assert_called_once_with(media_ids)
    
    @pytest.mark.asyncio
    async def test_bulk_delete_media_missing_media_ids(self, media_service):
        """Test bulk delete with missing media IDs"""
        with pytest.raises(ValidationError, match="Media IDs are required"):
            await media_service.bulk_delete_media([], "athlete123")
    
    @pytest.mark.asyncio
    async def test_bulk_delete_media_too_many_files(self, media_service):
        """Test bulk delete with too many files"""
        media_ids = ["media" + str(i) for i in range(51)]
        
        with pytest.raises(ValidationError, match="Maximum 50 files per bulk delete"):
            await media_service.bulk_delete_media(media_ids, "athlete123")
    
    # Test error handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, media_service, mock_media_create):
        """Test database error handling"""
        media_service.media_service.create = AsyncMock(side_effect=Exception("Database error"))
        
        with pytest.raises(DatabaseError, match="Failed to upload media"):
            await media_service.upload_media("athlete123", mock_media_create, "https://example.com/video.mp4")
    
    @pytest.mark.asyncio
    async def test_validation_error_propagation(self, media_service):
        """Test that validation errors are properly propagated"""
        with pytest.raises(ValidationError, match="Athlete ID is required"):
            await media_service.get_athlete_media("", 10, 0)
    
    @pytest.mark.asyncio
    async def test_resource_not_found_error_propagation(self, media_service):
        """Test that resource not found errors are properly propagated"""
        media_service.media_service.get_by_id = AsyncMock(return_value=None)
        
        with pytest.raises(ResourceNotFoundError, match="Media not found"):
            await media_service.get_media_by_id("media123")
    
    @pytest.mark.asyncio
    async def test_authorization_error_propagation(self, media_service, mock_media_data):
        """Test that authorization errors are properly propagated"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        
        with pytest.raises(AuthorizationError, match="Not authorized"):
            await media_service.delete_media("media123", "wrong_athlete")
    
    # Test URL validation
    @pytest.mark.asyncio
    async def test_url_validation_valid_urls(self, media_service):
        """Test URL validation with valid URLs"""
        valid_urls = [
            "https://example.com/video.mp4",
            "http://example.com/image.jpg",
            "gs://bucket/file.mp4"
        ]
        
        for url in valid_urls:
            assert media_service._is_valid_url(url) is True
    
    @pytest.mark.asyncio
    async def test_url_validation_invalid_urls(self, media_service):
        """Test URL validation with invalid URLs"""
        invalid_urls = [
            "",
            "invalid-url",
            "ftp://example.com/file.mp4",
            "https://",
            "http://"
        ]
        
        for url in invalid_urls:
            assert media_service._is_valid_url(url) is False
    
    # Test AI analysis
    @pytest.mark.asyncio
    async def test_analyze_media_success(self, media_service, mock_media_data):
        """Test successful AI analysis"""
        analysis_result = {
            "rating": "excellent",
            "summary": "Great performance",
            "detailed_analysis": {"technical_skills": 8.5},
            "confidence_score": 0.9
        }
        
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.ai_service.analyze_media = AsyncMock(return_value=analysis_result)
        media_service.media_service.update = AsyncMock()
        
        await media_service._analyze_media("media123")
        
        # Should be called twice: once for processing status, once for results
        assert media_service.media_service.update.call_count == 2
    
    @pytest.mark.asyncio
    async def test_analyze_media_failure(self, media_service, mock_media_data):
        """Test AI analysis failure with retry"""
        media_service.media_service.get_by_id = AsyncMock(return_value=mock_media_data)
        media_service.ai_service.analyze_media = AsyncMock(side_effect=Exception("AI service error"))
        media_service.media_service.update = AsyncMock()
        
        await media_service._analyze_media("media123")
        
        # Should be called for error status update
        media_service.media_service.update.assert_called()
    
    # Test rate limiting
    @pytest.mark.asyncio
    async def test_rate_limit_check(self, media_service):
        """Test rate limit checking"""
        media_service.media_service.count = AsyncMock(return_value=15)  # Under limit
        
        # Should not raise an exception
        await media_service._check_upload_rate_limit("athlete123")
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, media_service):
        """Test rate limit exceeded"""
        media_service.media_service.count = AsyncMock(return_value=20)  # At limit
        
        with pytest.raises(ValidationError, match="Rate limit exceeded"):
            await media_service._check_upload_rate_limit("athlete123") 