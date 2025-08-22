"""
Refactored Media Service - Main orchestrator for media operations
"""
import logging
from typing import Optional, List, Dict, Any

from .media_upload_service import MediaUploadService
from .media_query_service import MediaQueryService
from ..aiAgents.media_analysis_agent import MediaAnalysisAgent
from ..aiAgents.media_recommendation_agent import MediaRecommendationAgent
from ..models.media import MediaCreate, MediaUpdate
from ..models.media_responses import (
    MediaResponse, MediaListResponse, MediaStatusResponse, 
    BulkUploadResponse, RecommendationResponse
)
from ..config.media_config import get_media_config
from ..api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError

logger = logging.getLogger(__name__)


class MediaService:
    """
    Main Media Service that orchestrates specialized services
    
    This service acts as a facade, delegating specific operations to specialized services:
    - MediaUploadService: Handles upload operations
    - MediaQueryService: Handles query and retrieval operations  
    - MediaAnalysisAgent: Handles AI analysis operations
    - MediaRecommendationAgent: Handles recommendation operations
    """
    
    def __init__(self):
        self.config = get_media_config()
        self.upload_service = MediaUploadService()
        self.query_service = MediaQueryService()
        self.analysis_agent = MediaAnalysisAgent()
        self.recommendation_agent = MediaRecommendationAgent()
        
        # Configuration constants
        self.DEFAULT_MEDIA_LIMIT = self.config.get('default_media_limit', 100)
        self.MAX_MEDIA_LIMIT = self.config.get('max_media_limit', 1000)
        self.DEFAULT_RECOMMENDATION_LIMIT = self.config.get('default_recommendation_limit', 20)
        self.MAX_RECOMMENDATION_LIMIT = self.config.get('max_recommendation_limit', 100)
    
    # Upload Operations (delegated to MediaUploadService)
    
    async def upload_media(self, athlete_id: str, media_data: MediaCreate, file_url: str, thumbnail_url: Optional[str] = None) -> MediaResponse:
        """
        Upload media for athlete
        
        Args:
            athlete_id: ID of the athlete uploading the media
            media_data: Media creation data
            file_url: URL to the media file
            thumbnail_url: Optional URL to the thumbnail
            
        Returns:
            MediaResponse: Created media response
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If upload operation fails
        """
        return await self.upload_service.upload_media(athlete_id, media_data, file_url, thumbnail_url)
    
    async def bulk_upload_media(self, athlete_id: str, media_list: List[Dict[str, Any]]) -> BulkUploadResponse:
        """
        Bulk upload multiple media files
        
        Args:
            athlete_id: ID of the athlete uploading the media
            media_list: List of media data dictionaries
            
        Returns:
            BulkUploadResponse: Result of bulk upload operation
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If bulk upload operation fails
        """
        return await self.upload_service.bulk_upload_media(athlete_id, media_list)
    
    async def update_media(self, media_id: str, media_data: MediaUpdate, athlete_id: str) -> MediaResponse:
        """
        Update media metadata
        
        Args:
            media_id: ID of the media to update
            media_data: Updated media data
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            MediaResponse: Updated media response
            
        Raises:
            ValidationError: If input validation fails
            ResourceNotFoundError: If media not found
            AuthorizationError: If athlete not authorized
            DatabaseError: If update operation fails
        """
        return await self.upload_service.update_media(media_id, media_data, athlete_id)
    
    async def delete_media(self, media_id: str, athlete_id: str) -> bool:
        """
        Delete media
        
        Args:
            media_id: ID of the media to delete
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            bool: True if deletion successful
            
        Raises:
            ValidationError: If input validation fails
            ResourceNotFoundError: If media not found
            AuthorizationError: If athlete not authorized
            DatabaseError: If deletion operation fails
        """
        return await self.upload_service.delete_media(media_id, athlete_id)
    
    async def bulk_delete_media(self, media_ids: List[str], athlete_id: str) -> bool:
        """
        Bulk delete media files
        
        Args:
            media_ids: List of media IDs to delete
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            bool: True if bulk deletion successful
            
        Raises:
            ValidationError: If input validation fails
            AuthorizationError: If athlete not authorized
            DatabaseError: If bulk deletion operation fails
        """
        return await self.upload_service.bulk_delete_media(media_ids, athlete_id)
    
    # Query Operations (delegated to MediaQueryService)
    
    async def get_media_by_id(self, media_id: str) -> Optional[MediaResponse]:
        """
        Get media by ID
        
        Args:
            media_id: ID of the media to retrieve
            
        Returns:
            MediaResponse: Media response if found, None otherwise
            
        Raises:
            ValidationError: If media_id is invalid
            ResourceNotFoundError: If media not found
            DatabaseError: If retrieval operation fails
        """
        return await self.query_service.get_media_by_id(media_id)
    
    async def get_athlete_media(self, athlete_id: str, limit: int = None, offset: int = 0) -> MediaListResponse:
        """
        Get all media for an athlete
        
        Args:
            athlete_id: ID of the athlete
            limit: Maximum number of media items to return (defaults to config value)
            offset: Number of items to skip for pagination
            
        Returns:
            MediaListResponse: Paginated list of media items
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If retrieval operation fails
        """
        if limit is None:
            limit = self.DEFAULT_MEDIA_LIMIT
            
        if limit < 1 or limit > self.MAX_MEDIA_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_MEDIA_LIMIT}")
        if offset < 0:
            raise ValidationError("Offset must be non-negative")
            
        return await self.query_service.get_athlete_media(athlete_id, limit, offset)
    
    async def get_media_status(self, media_id: str, athlete_id: str) -> Optional[MediaStatusResponse]:
        """
        Get AI analysis status for media
        
        Args:
            media_id: ID of the media
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            MediaStatusResponse: Media status if found and authorized, None otherwise
            
        Raises:
            ValidationError: If input validation fails
            ResourceNotFoundError: If media not found
            AuthorizationError: If athlete not authorized
            DatabaseError: If retrieval operation fails
        """
        return await self.query_service.get_media_status(media_id, athlete_id)
    
    async def search_media(self, query: str, media_type: Optional[str] = None, 
                          sport_category: Optional[str] = None, limit: int = 50, 
                          offset: int = 0) -> MediaListResponse:
        """
        Search media by various criteria
        
        Args:
            query: Search query string
            media_type: Optional media type filter
            sport_category: Optional sport category filter
            limit: Maximum number of results to return
            offset: Number of items to skip for pagination
            
        Returns:
            MediaListResponse: Paginated search results
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If search operation fails
        """
        if not query or not query.strip():
            raise ValidationError("Search query is required")
        if limit < 1 or limit > self.MAX_MEDIA_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_MEDIA_LIMIT}")
        if offset < 0:
            raise ValidationError("Offset must be non-negative")
            
        return await self.query_service.search_media(query, media_type, sport_category, limit, offset)
    
    async def get_media_by_type(self, media_type: str, limit: int = 50, 
                               offset: int = 0, moderation_status: str = "approved") -> MediaListResponse:
        """
        Get media by type with optional moderation status filter
        
        Args:
            media_type: Type of media to retrieve
            limit: Maximum number of results to return
            offset: Number of items to skip for pagination
            moderation_status: Moderation status filter
            
        Returns:
            MediaListResponse: Paginated list of media items
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If retrieval operation fails
        """
        if not media_type:
            raise ValidationError("Media type is required")
        if limit < 1 or limit > self.MAX_MEDIA_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_MEDIA_LIMIT}")
        if offset < 0:
            raise ValidationError("Offset must be non-negative")
            
        return await self.query_service.get_media_by_type(media_type, limit, offset, moderation_status)
    
    # AI Analysis Operations (delegated to MediaAnalysisAgent)
    
    async def retry_ai_analysis(self, media_id: str, athlete_id: str) -> bool:
        """
        Retry AI analysis for failed media
        
        Args:
            media_id: ID of the media to retry analysis for
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            bool: True if retry initiated successfully
            
        Raises:
            ValidationError: If input validation fails
            ResourceNotFoundError: If media not found
            AuthorizationError: If athlete not authorized
            DatabaseError: If retry operation fails
        """
        if not media_id:
            raise ValidationError("Media ID is required")
        if not athlete_id:
            raise ValidationError("Athlete ID is required")
            
        try:
            # Check ownership first
            media_doc = await self.query_service.get_media_by_id(media_id)
            if media_doc.athlete_id != athlete_id:
                raise AuthorizationError("Not authorized to retry analysis for this media")
            
            return await self.analysis_agent.retry_analysis(media_id)
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error retrying AI analysis for media {media_id}: {e}")
            raise DatabaseError(f"Failed to retry AI analysis: {str(e)}")
    
    async def get_ai_analysis_status(self, media_id: str) -> Optional[Dict[str, Any]]:
        """
        Get AI analysis status for media (internal use)
        
        Args:
            media_id: ID of the media
            
        Returns:
            Dict[str, Any]: AI analysis status if found, None otherwise
            
        Raises:
            ValidationError: If media_id is invalid
            DatabaseError: If retrieval operation fails
        """
        if not media_id:
            raise ValidationError("Media ID is required")
            
        try:
            media_doc = await self.query_service.get_media_by_id(media_id)
            return media_doc.ai_analysis if media_doc else None
        except Exception as e:
            logger.error(f"Error getting AI analysis status for media {media_id}: {e}")
            raise DatabaseError(f"Failed to get AI analysis status: {str(e)}")
    
    # Recommendation Operations (delegated to MediaRecommendationAgent)
    
    async def get_recommended_reels(self, scout_id: str, limit: int = None) -> List[MediaResponse]:
        """
        Get recommended reels for scout
        
        Args:
            scout_id: ID of the scout
            limit: Maximum number of recommendations to return (defaults to config value)
            
        Returns:
            List[MediaResponse]: List of recommended reels
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If recommendation operation fails
        """
        if not scout_id:
            raise ValidationError("Scout ID is required")
        if limit is None:
            limit = self.DEFAULT_RECOMMENDATION_LIMIT
        if limit < 1 or limit > self.MAX_RECOMMENDATION_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_RECOMMENDATION_LIMIT}")
            
        try:
            reels_data = await self.recommendation_agent.get_recommended_reels(scout_id, limit)
            return self._convert_media_data_to_responses(reels_data)
            
        except Exception as e:
            logger.error(f"Error getting recommended reels for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to get recommended reels: {str(e)}")
    
    async def get_recommended_media_by_sport(self, sport_category: str, limit: int = None) -> List[MediaResponse]:
        """
        Get recommended media by sport category
        
        Args:
            sport_category: Sport category for recommendations
            limit: Maximum number of recommendations to return (defaults to config value)
            
        Returns:
            List[MediaResponse]: List of recommended media items
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If recommendation operation fails
        """
        if not sport_category:
            raise ValidationError("Sport category is required")
        if limit is None:
            limit = self.DEFAULT_RECOMMENDATION_LIMIT
        if limit < 1 or limit > self.MAX_RECOMMENDATION_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_RECOMMENDATION_LIMIT}")
            
        try:
            media_data = await self.recommendation_agent.get_recommended_media_by_sport(sport_category, limit)
            return self._convert_media_data_to_responses(media_data)
            
        except Exception as e:
            logger.error(f"Error getting recommended media by sport {sport_category}: {e}")
            raise DatabaseError(f"Failed to get recommended media: {str(e)}")
    
    async def get_trending_media(self, limit: int = None, time_window_hours: int = 24) -> List[MediaResponse]:
        """
        Get trending media based on recent activity
        
        Args:
            limit: Maximum number of recommendations to return (defaults to config value)
            time_window_hours: Time window for trending calculation in hours
            
        Returns:
            List[MediaResponse]: List of trending media items
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If recommendation operation fails
        """
        if limit is None:
            limit = self.DEFAULT_RECOMMENDATION_LIMIT
        if limit < 1 or limit > self.MAX_RECOMMENDATION_LIMIT:
            raise ValidationError(f"Limit must be between 1 and {self.MAX_RECOMMENDATION_LIMIT}")
        if time_window_hours < 1 or time_window_hours > 168:  # Max 1 week
            raise ValidationError("Time window must be between 1 and 168 hours")
            
        try:
            media_data = await self.recommendation_agent.get_trending_media(limit, time_window_hours)
            return self._convert_media_data_to_responses(media_data)
            
        except Exception as e:
            logger.error(f"Error getting trending media: {e}")
            raise DatabaseError(f"Failed to get trending media: {str(e)}")
    
    # Helper Methods
    
    def _convert_media_data_to_responses(self, media_data_list: List[Dict[str, Any]]) -> List[MediaResponse]:
        """
        Convert raw media data to MediaResponse objects
        
        Args:
            media_data_list: List of raw media data dictionaries
            
        Returns:
            List[MediaResponse]: List of converted MediaResponse objects
        """
        responses = []
        for media_data in media_data_list:
            try:
                response = MediaResponse(
                    id=media_data["id"],
                    athlete_id=media_data["athlete_id"],
                    type=media_data["type"],
                    url=media_data["url"],
                    thumbnail_url=media_data.get("thumbnail_url"),
                    description=media_data.get("description"),
                    moderation_status=media_data["moderation_status"],
                    created_at=media_data["created_at"],
                    ai_analysis=media_data.get("ai_analysis", {})
                )
                responses.append(response)
            except Exception as e:
                logger.warning(f"Error converting media data: {e}")
                continue
        return responses
    
    # Utility Operations
    
    async def get_upload_rate_limit_info(self, athlete_id: str) -> Dict[str, Any]:
        """
        Get upload rate limit information for athlete
        
        Args:
            athlete_id: ID of the athlete
            
        Returns:
            Dict[str, Any]: Rate limit information
            
        Raises:
            ValidationError: If athlete_id is invalid
        """
        if not athlete_id:
            raise ValidationError("Athlete ID is required")
            
        return await self.upload_service.get_upload_rate_limit_info(athlete_id)
    
    async def cleanup_background_tasks(self) -> None:
        """Clean up background tasks from AI analysis"""
        await self.analysis_agent.cleanup_background_tasks()
    
    def get_background_task_count(self) -> int:
        """Get count of active background tasks"""
        return self.analysis_agent.get_background_task_count()
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all media services"""
        return {
            "upload_service": "active",
            "query_service": "active", 
            "analysis_agent": "active",
            "recommendation_agent": "active",
            "background_tasks": self.get_background_task_count(),
            "config": {
                "max_uploads_per_hour": self.config['max_uploads_per_hour'],
                "supported_types": self.config['supported_types'],
                "ai_analysis_max_retries": self.config['ai_analysis_max_retries'],
                "default_media_limit": self.DEFAULT_MEDIA_LIMIT,
                "max_media_limit": self.MAX_MEDIA_LIMIT,
                "default_recommendation_limit": self.DEFAULT_RECOMMENDATION_LIMIT,
                "max_recommendation_limit": self.MAX_RECOMMENDATION_LIMIT
            }
        } 