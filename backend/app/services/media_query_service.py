"""
Media query service for retrieving and searching media
"""
import logging
from typing import Optional, List, Dict, Any

from ..models.media_responses import MediaResponse, MediaListResponse, MediaStatusResponse
from ..services.database_service import DatabaseService
from ..config.media_config import get_media_config
from ..api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class MediaQueryService:
    """Service for handling media query and retrieval operations"""
    
    def __init__(self):
        self.database_service = DatabaseService("media")
        self.config = get_media_config()
        
        # Configuration constants
        self.DEFAULT_MEDIA_LIMIT = self.config.get('default_media_limit', 100)
        self.MAX_MEDIA_LIMIT = self.config.get('max_media_limit', 1000)
        self.DEFAULT_SEARCH_LIMIT = self.config.get('default_search_limit', 50)
        self.MAX_SEARCH_LIMIT = self.config.get('max_search_limit', 200)
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration values"""
        if 'supported_types' not in self.config:
            raise ValueError("Missing 'supported_types' in configuration")
        if not self.config['supported_types']:
            raise ValueError("'supported_types' cannot be empty")
        
        # Validate limit configurations
        if self.MAX_MEDIA_LIMIT <= self.DEFAULT_MEDIA_LIMIT:
            raise ValueError("MAX_MEDIA_LIMIT must be greater than DEFAULT_MEDIA_LIMIT")
        if self.MAX_SEARCH_LIMIT <= self.DEFAULT_SEARCH_LIMIT:
            raise ValueError("MAX_SEARCH_LIMIT must be greater than DEFAULT_SEARCH_LIMIT")
    
    async def get_media_by_id(self, media_id: str) -> MediaResponse:
        """
        Get media by ID
        
        Args:
            media_id: Unique identifier for the media
            
        Returns:
            MediaResponse: Media response if found
            
        Raises:
            ValidationError: If media_id is invalid
            ResourceNotFoundError: If media not found
            DatabaseError: If retrieval operation fails
        """
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            
            media_doc = await self.database_service.get_by_id(media_id)
            if not media_doc:
                raise ResourceNotFoundError("Media not found", media_id)
            
            return await self._convert_to_media_response(media_doc)
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting media by ID {media_id}: {e}")
            raise DatabaseError(f"Failed to get media: {str(e)}")
    
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
        try:
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            if limit is None:
                limit = self.DEFAULT_MEDIA_LIMIT
                
            if limit < 1 or limit > self.MAX_MEDIA_LIMIT:
                raise ValidationError(f"Limit must be between 1 and {self.MAX_MEDIA_LIMIT}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            media_docs = await self.database_service.query(filters, limit, offset)
            
            # Convert to response models using helper method
            media_responses = await self._convert_multiple_media_docs(media_docs)
            
            # Get total count
            total_count = await self.database_service.count(filters)
            
            return MediaListResponse(
                media=media_responses,
                total_count=total_count,
                limit=limit,
                offset=offset
            )
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting athlete media for {athlete_id}: {e}")
            raise DatabaseError(f"Failed to get athlete media: {str(e)}")
    
    async def get_media_status(self, media_id: str, athlete_id: str) -> MediaStatusResponse:
        """
        Get AI analysis status for media
        
        Args:
            media_id: ID of the media
            athlete_id: ID of the athlete (for authorization)
            
        Returns:
            MediaStatusResponse: Media status if found and authorized
            
        Raises:
            ValidationError: If input validation fails
            ResourceNotFoundError: If media not found
            AuthorizationError: If athlete not authorized
            DatabaseError: If retrieval operation fails
        """
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            media_doc = await self.database_service.get_by_id(media_id)
            if not media_doc:
                raise ResourceNotFoundError("Media not found", media_id)
            
            # Check ownership
            if media_doc["athlete_id"] != athlete_id:
                raise AuthorizationError("Not authorized to access this media")
            
            return MediaStatusResponse(
                media_id=media_id,
                ai_analysis=media_doc.get("ai_analysis", {})
            )
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error getting media status for {media_id}: {e}")
            raise DatabaseError(f"Failed to get media status: {str(e)}")
    
    async def search_media(self, query: str, media_type: Optional[str] = None, 
                          sport_category: Optional[str] = None, limit: int = None, 
                          offset: int = 0) -> MediaListResponse:
        """
        Search media by various criteria
        
        Args:
            query: Search query string
            media_type: Optional media type filter
            sport_category: Optional sport category filter
            limit: Maximum number of results to return (defaults to config value)
            offset: Number of items to skip for pagination
            
        Returns:
            MediaListResponse: Paginated search results
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If search operation fails
        """
        try:
            if not query or not query.strip():
                raise ValidationError("Search query is required")
            
            if limit is None:
                limit = self.DEFAULT_SEARCH_LIMIT
                
            if limit < 1 or limit > self.MAX_SEARCH_LIMIT:
                raise ValidationError(f"Limit must be between 1 and {self.MAX_SEARCH_LIMIT}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Build filters
            filters = [
                FieldFilter("moderation_status", "==", "approved")
            ]
            
            if media_type:
                filters.append(FieldFilter("type", "==", media_type))
            
            if sport_category:
                # Note: This assumes sport_category field exists
                filters.append(FieldFilter("sport_category", "==", sport_category))
            
            # For now, we'll do basic filtering
            # In production, you'd want to implement full-text search
            media_docs = await self.database_service.query(filters, limit * 2, offset)
            
            # Filter by query (basic implementation)
            # In production, use a proper search engine like Elasticsearch
            filtered_media = self._filter_media_by_query(media_docs, query, limit)
            
            # Convert to response models using helper method
            media_responses = await self._convert_multiple_media_docs(filtered_media)
            
            # Get total count for pagination
            total_count = len(filtered_media)  # Simplified for now
            
            return MediaListResponse(
                media=media_responses,
                total_count=total_count,
                limit=limit,
                offset=offset
            )
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error searching media: {e}")
            raise DatabaseError(f"Failed to search media: {str(e)}")
    
    async def get_media_by_type(self, media_type: str, limit: int = None, 
                               offset: int = 0, moderation_status: str = "approved") -> MediaListResponse:
        """
        Get media by type with optional moderation status filter
        
        Args:
            media_type: Type of media to retrieve
            limit: Maximum number of results to return (defaults to config value)
            offset: Number of items to skip for pagination
            moderation_status: Moderation status filter
            
        Returns:
            MediaListResponse: Paginated list of media items
            
        Raises:
            ValidationError: If input validation fails
            DatabaseError: If retrieval operation fails
        """
        try:
            if limit is None:
                limit = self.DEFAULT_SEARCH_LIMIT
                
            if limit < 1 or limit > self.MAX_SEARCH_LIMIT:
                raise ValidationError(f"Limit must be between 1 and {self.MAX_SEARCH_LIMIT}")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            # Build filters
            filters = []
            
            # Handle media type filter
            if media_type and media_type != "all" and media_type in self.config['supported_types']:
                filters.append(FieldFilter("type", "==", media_type))
            elif media_type and media_type != "all":
                raise ValidationError(f"Invalid media type. Must be one of: {self.config['supported_types']}")
            
            # Handle moderation status filter
            if moderation_status and moderation_status != "all":
                filters.append(FieldFilter("moderation_status", "==", moderation_status))
            
            # If no filters, get all media
            if not filters:
                media_docs = await self.database_service.query([], limit, offset)
            else:
                media_docs = await self.database_service.query(filters, limit, offset)
            
            # Convert to response models using helper method
            media_responses = await self._convert_multiple_media_docs(media_docs)
            
            # Get total count
            if not filters:
                total_count = await self.database_service.count([])
            else:
                total_count = await self.database_service.count(filters)
            
            return MediaListResponse(
                media=media_responses,
                total_count=total_count,
                limit=limit,
                offset=offset
            )
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting media by type {media_type}: {e}")
            raise DatabaseError(f"Failed to get media by type: {str(e)}")
    
    # Helper Methods
    
    async def _convert_multiple_media_docs(self, media_docs: List[Dict[str, Any]]) -> List[MediaResponse]:
        """
        Convert multiple media documents to responses, skipping invalid ones
        
        Args:
            media_docs: List of media document dictionaries
            
        Returns:
            List[MediaResponse]: List of converted media responses
        """
        responses = []
        for media_doc in media_docs:
            try:
                response = await self._convert_to_media_response(media_doc)
                responses.append(response)
            except Exception as e:
                logger.warning(f"Error converting media doc {media_doc.get('id')}: {e}")
                continue
        return responses
    
    def _filter_media_by_query(self, media_docs: List[Dict[str, Any]], query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Filter media documents by search query
        
        Args:
            media_docs: List of media document dictionaries
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: Filtered media documents
        """
        filtered_media = []
        query_lower = query.lower()
        
        for media_doc in media_docs:
            # Check description, type, and other searchable fields
            description = media_doc.get("description", "").lower()
            media_type = media_doc.get("type", "").lower()
            
            if (query_lower in description or 
                query_lower in media_type or
                query_lower in str(media_doc.get("sport_category", "")).lower()):
                filtered_media.append(media_doc)
            
            if len(filtered_media) >= limit:
                break
        
        return filtered_media
    
    async def _convert_to_media_response(self, media_doc: Dict[str, Any]) -> MediaResponse:
        """
        Convert database document to MediaResponse
        
        Args:
            media_doc: Media document dictionary from database
            
        Returns:
            MediaResponse: Converted media response
            
        Raises:
            DatabaseError: If conversion fails due to invalid document format
        """
        try:
            return MediaResponse(
                id=media_doc["id"],
                athlete_id=media_doc["athlete_id"],
                type=media_doc["type"],
                url=media_doc["url"],
                thumbnail_url=media_doc.get("thumbnail_url"),
                description=media_doc.get("description"),
                moderation_status=media_doc["moderation_status"],
                created_at=media_doc["created_at"],
                ai_analysis=media_doc.get("ai_analysis", {})
            )
        except KeyError as e:
            logger.error(f"Missing required field in media document: {e}")
            raise DatabaseError(f"Invalid media document format: missing {e}")
        except Exception as e:
            logger.error(f"Error converting media document: {e}")
            raise DatabaseError(f"Failed to convert media document: {str(e)}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get service status and configuration information
        
        Returns:
            Dict[str, Any]: Service status information
        """
        return {
            "service": "MediaQueryService",
            "status": "active",
            "database_service": "active",
            "config": {
                "default_media_limit": self.DEFAULT_MEDIA_LIMIT,
                "max_media_limit": self.MAX_MEDIA_LIMIT,
                "default_search_limit": self.DEFAULT_SEARCH_LIMIT,
                "max_search_limit": self.MAX_SEARCH_LIMIT,
                "supported_types": self.config['supported_types']
            }
        } 