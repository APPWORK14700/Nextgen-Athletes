from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from ..models.media import Media, MediaCreate, MediaUpdate, AIAnalysis
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from .ai_service import AIService
from firebase_admin.firestore import FieldFilter
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError, AuthorizationError

logger = logging.getLogger(__name__)


class MediaService:
    """Media service for managing athlete media uploads and AI analysis"""
    
    def __init__(self):
        self.media_service = DatabaseService("media")
        self.ai_service = AIService()
        self.max_uploads_per_hour = 20  # Rate limiting
        self.max_file_size_mb = 100  # Maximum file size in MB
        self.supported_types = ["video", "image", "reel"]
        self.supported_formats = {
            "video": ["mp4", "mov", "avi"],
            "image": ["jpg", "jpeg", "png", "gif"],
            "reel": ["mp4", "mov"]
        }
    
    async def upload_media(self, athlete_id: str, media_data: MediaCreate, file_url: str, thumbnail_url: Optional[str] = None) -> Dict[str, Any]:
        """Upload media for athlete"""
        try:
            # Input validation
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            if not media_data.type:
                raise ValidationError("Media type is required")
            if not file_url or not file_url.strip():
                raise ValidationError("File URL is required")
            
            # Validate media type
            if media_data.type not in self.supported_types:
                raise ValidationError(f"Invalid media type. Must be one of: {self.supported_types}")
            
            # Validate file URL format
            if not self._is_valid_url(file_url):
                raise ValidationError("Invalid file URL format")
            
            if thumbnail_url and not self._is_valid_url(thumbnail_url):
                raise ValidationError("Invalid thumbnail URL format")
            
            # Check rate limiting
            await self._check_upload_rate_limit(athlete_id)
            
            # Create media document
            media_doc = {
                "athlete_id": athlete_id,
                "type": media_data.type,
                "url": file_url.strip(),
                "thumbnail_url": thumbnail_url.strip() if thumbnail_url else None,
                "description": media_data.description.strip() if media_data.description else None,
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
            
            media_id = await self.media_service.create(media_doc)
            
            # Trigger AI analysis asynchronously
            asyncio.create_task(self._analyze_media(media_id))
            
            return await self.get_media_by_id(media_id)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error uploading media for athlete {athlete_id}: {e}")
            raise DatabaseError(f"Failed to upload media: {str(e)}")
    
    async def get_media_by_id(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Get media by ID"""
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            
            media_doc = await self.media_service.get_by_id(media_id)
            if not media_doc:
                raise ResourceNotFoundError("Media not found", media_id)
            
            return media_doc
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting media by ID {media_id}: {e}")
            raise DatabaseError(f"Failed to get media: {str(e)}")
    
    async def get_athlete_media(self, athlete_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all media for an athlete"""
        try:
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            if limit < 1 or limit > 1000:
                raise ValidationError("Limit must be between 1 and 1000")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            filters = [FieldFilter("athlete_id", "==", athlete_id)]
            media = await self.media_service.query(filters, limit, offset)
            return media
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting athlete media for {athlete_id}: {e}")
            raise DatabaseError(f"Failed to get athlete media: {str(e)}")
    
    async def update_media(self, media_id: str, media_data: MediaUpdate, athlete_id: str) -> Dict[str, Any]:
        """Update media metadata"""
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            # Check ownership
            media_doc = await self.get_media_by_id(media_id)
            if media_doc["athlete_id"] != athlete_id:
                raise AuthorizationError("Not authorized to update this media")
            
            update_data = {}
            
            if media_data.description is not None:
                update_data["description"] = media_data.description.strip() if media_data.description else None
            
            if update_data:
                await self.media_service.update(media_id, update_data)
            
            return await self.get_media_by_id(media_id)
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error updating media {media_id}: {e}")
            raise DatabaseError(f"Failed to update media: {str(e)}")
    
    async def delete_media(self, media_id: str, athlete_id: str) -> bool:
        """Delete media"""
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            # Check ownership
            media_doc = await self.get_media_by_id(media_id)
            if media_doc["athlete_id"] != athlete_id:
                raise AuthorizationError("Not authorized to delete this media")
            
            await self.media_service.delete(media_id)
            return True
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error deleting media {media_id}: {e}")
            raise DatabaseError(f"Failed to delete media: {str(e)}")
    
    async def get_media_status(self, media_id: str, athlete_id: str) -> Optional[Dict[str, Any]]:
        """Get AI analysis status for media"""
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            media_doc = await self.get_media_by_id(media_id)
            if not media_doc:
                raise ResourceNotFoundError("Media not found", media_id)
            
            # Check ownership
            if media_doc["athlete_id"] != athlete_id:
                raise AuthorizationError("Not authorized to access this media")
            
            return {
                "media_id": media_id,
                "ai_analysis": media_doc.get("ai_analysis", {})
            }
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error getting media status for {media_id}: {e}")
            raise DatabaseError(f"Failed to get media status: {str(e)}")
    
    async def retry_ai_analysis(self, media_id: str, athlete_id: str) -> bool:
        """Retry AI analysis for failed media"""
        try:
            if not media_id:
                raise ValidationError("Media ID is required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            media_doc = await self.get_media_by_id(media_id)
            if not media_doc:
                raise ResourceNotFoundError("Media not found", media_id)
            
            # Check ownership
            if media_doc["athlete_id"] != athlete_id:
                raise AuthorizationError("Not authorized to retry analysis for this media")
            
            ai_analysis = media_doc.get("ai_analysis", {})
            
            # Check if we can retry
            retry_count = ai_analysis.get("retry_count", 0)
            max_retries = ai_analysis.get("max_retries", 5)
            
            if retry_count >= max_retries:
                raise ValidationError("Maximum retry attempts reached")
            
            # Reset AI analysis status
            update_data = {
                "ai_analysis": {
                    "status": "pending",
                    "rating": None,
                    "summary": None,
                    "detailed_analysis": None,
                    "sport_specific_metrics": None,
                    "confidence_score": None,
                    "analysis_started_at": None,
                    "analysis_completed_at": None,
                    "retry_count": retry_count + 1,
                    "max_retries": max_retries,
                    "next_retry_at": None,
                    "error_message": None
                }
            }
            
            await self.media_service.update(media_id, update_data)
            
            # Trigger AI analysis asynchronously
            asyncio.create_task(self._analyze_media(media_id))
            
            return True
            
        except (ValidationError, ResourceNotFoundError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Error retrying AI analysis for media {media_id}: {e}")
            raise DatabaseError(f"Failed to retry AI analysis: {str(e)}")
    
    async def get_recommended_reels(self, scout_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recommended reels for scout"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required")
            
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            # This is a simplified recommendation algorithm
            # In production, you'd want to implement a more sophisticated recommendation system
            
            # Get all reels with approved moderation status
            filters = [
                FieldFilter("type", "==", "reel"),
                FieldFilter("moderation_status", "==", "approved")
            ]
            
            reels = await self.media_service.query(filters, limit * 2)  # Get more to filter
            
            # For now, just return reels with completed AI analysis
            # In production, you'd want to consider:
            # - Scout's focus areas
            # - Athlete ratings
            # - Location preferences
            # - Sport category preferences
            
            recommended_reels = []
            for reel in reels:
                ai_analysis = reel.get("ai_analysis", {})
                if ai_analysis.get("status") == "completed":
                    recommended_reels.append(reel)
                    if len(recommended_reels) >= limit:
                        break
            
            return recommended_reels
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting recommended reels for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to get recommended reels: {str(e)}")
    
    async def bulk_upload_media(self, athlete_id: str, media_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk upload multiple media files"""
        try:
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            if not media_list:
                raise ValidationError("Media list is required")
            
            if len(media_list) > 10:
                raise ValidationError("Maximum 10 files per bulk upload")
            
            # Check rate limiting
            await self._check_upload_rate_limit(athlete_id)
            
            uploaded_count = 0
            failed_count = 0
            media_ids = []
            errors = []
            
            # Process uploads concurrently for better performance
            upload_tasks = []
            for media_item in media_list:
                task = self._process_single_upload(athlete_id, media_item)
                upload_tasks.append(task)
            
            # Wait for all uploads to complete
            results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    errors.append(f"Failed to upload media {i+1}: {str(result)}")
                else:
                    uploaded_count += 1
                    media_ids.append(result["id"])
            
            return {
                "uploaded_count": uploaded_count,
                "failed_count": failed_count,
                "media_ids": media_ids,
                "errors": errors
            }
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error bulk uploading media for athlete {athlete_id}: {e}")
            raise DatabaseError(f"Failed to bulk upload media: {str(e)}")
    
    async def bulk_delete_media(self, media_ids: List[str], athlete_id: str) -> bool:
        """Bulk delete media files"""
        try:
            if not media_ids:
                raise ValidationError("Media IDs are required")
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            if len(media_ids) > 50:
                raise ValidationError("Maximum 50 files per bulk delete")
            
            # Validate ownership for all media
            valid_media_ids = []
            for media_id in media_ids:
                try:
                    media_doc = await self.get_media_by_id(media_id)
                    if media_doc["athlete_id"] == athlete_id:
                        valid_media_ids.append(media_id)
                    else:
                        logger.warning(f"Media {media_id} not owned by athlete {athlete_id}")
                except ResourceNotFoundError:
                    logger.warning(f"Media {media_id} not found")
                    continue
            
            if valid_media_ids:
                await self.media_service.batch_delete(valid_media_ids)
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error bulk deleting media: {e}")
            raise DatabaseError(f"Failed to bulk delete media: {str(e)}")
    
    async def _analyze_media(self, media_id: str) -> None:
        """Analyze media with AI (background task)"""
        try:
            # Update status to processing
            await self.media_service.update(media_id, {
                "ai_analysis.analysis_started_at": datetime.now(timezone.utc).isoformat(),
                "ai_analysis.status": "processing"
            })
            
            # Get media data
            media_doc = await self.media_service.get_by_id(media_id)
            if not media_doc:
                logger.error(f"Media {media_id} not found for analysis")
                return
            
            # Perform AI analysis
            analysis_result = await self.ai_service.analyze_media(
                media_doc["url"],
                media_doc["type"]
            )
            
            # Update with analysis results
            update_data = {
                "ai_analysis.status": "completed",
                "ai_analysis.rating": analysis_result.get("rating"),
                "ai_analysis.summary": analysis_result.get("summary"),
                "ai_analysis.detailed_analysis": analysis_result.get("detailed_analysis"),
                "ai_analysis.sport_specific_metrics": analysis_result.get("sport_specific_metrics"),
                "ai_analysis.confidence_score": analysis_result.get("confidence_score"),
                "ai_analysis.analysis_completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.media_service.update(media_id, update_data)
            
        except Exception as e:
            logger.error(f"Error analyzing media {media_id}: {e}")
            
            # Update with error status
            try:
                media_doc = await self.media_service.get_by_id(media_id)
                if media_doc:
                    ai_analysis = media_doc.get("ai_analysis", {})
                    retry_count = ai_analysis.get("retry_count", 0)
                    max_retries = ai_analysis.get("max_retries", 5)
                    
                    if retry_count < max_retries:
                        # Schedule retry with exponential backoff
                        next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** retry_count)
                        update_data = {
                            "ai_analysis.status": "retrying",
                            "ai_analysis.retry_count": retry_count + 1,
                            "ai_analysis.next_retry_at": next_retry_at.isoformat(),
                            "ai_analysis.error_message": str(e)
                        }
                    else:
                        # Mark as failed
                        update_data = {
                            "ai_analysis.status": "failed",
                            "ai_analysis.error_message": str(e)
                        }
                    
                    await self.media_service.update(media_id, update_data)
                    
                    # Schedule retry if needed
                    if retry_count < max_retries:
                        asyncio.create_task(self._schedule_retry(media_id, next_retry_at))
                        
            except Exception as retry_error:
                logger.error(f"Error updating media {media_id} with error status: {retry_error}")
    
    async def _schedule_retry(self, media_id: str, retry_at: datetime) -> None:
        """Schedule retry for failed AI analysis"""
        try:
            # Wait until retry time
            wait_seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            # Retry analysis
            await self._analyze_media(media_id)
            
        except Exception as e:
            logger.error(f"Error in scheduled retry for media {media_id}: {e}")
    
    async def _process_single_upload(self, athlete_id: str, media_item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single media upload (helper for bulk upload)"""
        try:
            media_data = MediaCreate(**media_item["metadata"])
            file_url = media_item["file_url"]
            thumbnail_url = media_item.get("thumbnail_url")
            
            return await self.upload_media(athlete_id, media_data, file_url, thumbnail_url)
            
        except Exception as e:
            logger.error(f"Error processing single upload: {e}")
            raise
    
    async def _check_upload_rate_limit(self, athlete_id: str) -> None:
        """Check rate limiting for media uploads"""
        try:
            # Get uploads in the last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            filters = [
                FieldFilter("athlete_id", "==", athlete_id),
                FieldFilter("created_at", ">=", one_hour_ago.isoformat())
            ]
            
            recent_count = await self.media_service.count(filters)
            if recent_count >= self.max_uploads_per_hour:
                raise ValidationError(f"Rate limit exceeded. Maximum {self.max_uploads_per_hour} uploads per hour.")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error checking upload rate limit for athlete {athlete_id}: {e}")
            # Don't fail the main operation due to rate limit check failure
            pass
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        if not url or not url.strip():
            return False
        
        # Basic URL validation
        url = url.strip()
        return url.startswith(('http://', 'https://', 'gs://')) and len(url) > 10 