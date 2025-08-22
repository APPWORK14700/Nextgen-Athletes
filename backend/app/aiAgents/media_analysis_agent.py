"""
AI Agent for handling media analysis operations
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from ..services.database_service import DatabaseService
from ..services.ai_service import AIService
from ..config.media_config import get_media_config
from ..api.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class MediaAnalysisAgent:
    """AI Agent responsible for analyzing media content"""
    
    def __init__(self):
        self.database_service = DatabaseService("media")
        self.ai_service = AIService()
        self.config = get_media_config()
        self._background_tasks: set[asyncio.Task] = set()
    
    async def analyze_media(self, media_id: str) -> None:
        """Analyze media with AI (background task)"""
        try:
            # Update status to processing
            await self.database_service.update(media_id, {
                "ai_analysis.analysis_started_at": datetime.now(timezone.utc).isoformat(),
                "ai_analysis.status": "processing"
            })
            
            # Get media data
            media_doc = await self.database_service.get_by_id(media_id)
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
            
            await self.database_service.update(media_id, update_data)
            logger.info(f"AI analysis completed for media {media_id}")
            
        except Exception as e:
            logger.error(f"Error analyzing media {media_id}: {e}")
            await self._handle_analysis_error(media_id, e)
    
    async def retry_analysis(self, media_id: str) -> bool:
        """Retry AI analysis for failed media"""
        try:
            media_doc = await self.database_service.get_by_id(media_id)
            if not media_doc:
                logger.error(f"Media {media_id} not found for retry")
                return False
            
            ai_analysis = media_doc.get("ai_analysis", {})
            retry_count = ai_analysis.get("retry_count", 0)
            max_retries = self.config['ai_analysis_max_retries']
            
            if retry_count >= max_retries:
                logger.warning(f"Maximum retry attempts reached for media {media_id}")
                return False
            
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
            
            await self.database_service.update(media_id, update_data)
            
            # Trigger AI analysis asynchronously
            await self._create_background_task(self.analyze_media(media_id))
            
            return True
            
        except Exception as e:
            logger.error(f"Error retrying AI analysis for media {media_id}: {e}")
            return False
    
    async def _handle_analysis_error(self, media_id: str, error: Exception) -> None:
        """Handle errors during AI analysis"""
        try:
            media_doc = await self.database_service.get_by_id(media_id)
            if not media_doc:
                return
            
            ai_analysis = media_doc.get("ai_analysis", {})
            retry_count = ai_analysis.get("retry_count", 0)
            max_retries = self.config['ai_analysis_max_retries']
            
            if retry_count < max_retries:
                # Schedule retry with exponential backoff
                delay_seconds = min(
                    self.config['ai_analysis_retry_delay_base_seconds'] * (2 ** retry_count),
                    self.config['ai_analysis_max_delay_seconds']
                )
                next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                
                update_data = {
                    "ai_analysis.status": "retrying",
                    "ai_analysis.retry_count": retry_count + 1,
                    "ai_analysis.next_retry_at": next_retry_at.isoformat(),
                    "ai_analysis.error_message": str(error)
                }
                
                await self.database_service.update(media_id, update_data)
                
                # Schedule retry
                await self._create_background_task(self._schedule_retry(media_id, next_retry_at))
            else:
                # Mark as failed
                update_data = {
                    "ai_analysis.status": "failed",
                    "ai_analysis.error_message": str(error)
                }
                await self.database_service.update(media_id, update_data)
                
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
            await self.analyze_media(media_id)
            
        except Exception as e:
            logger.error(f"Error in scheduled retry for media {media_id}: {e}")
    
    async def _create_background_task(self, coro) -> None:
        """Create and track background task"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
    
    async def cleanup_background_tasks(self) -> None:
        """Clean up completed background tasks"""
        # Remove completed tasks
        self._background_tasks = {task for task in self._background_tasks if not task.done()}
        
        # Cancel remaining tasks if needed
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for cancellation to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
    
    def get_background_task_count(self) -> int:
        """Get count of active background tasks"""
        return len(self._background_tasks) 