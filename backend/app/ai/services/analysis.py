"""
Media analysis service using AI providers
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..providers.base import AIProvider
from ...config.ai_config import AIConfig

logger = logging.getLogger(__name__)

class MediaAnalysisService:
    """Service for analyzing athlete media using AI providers"""
    
    def __init__(self, ai_provider: AIProvider, config: AIConfig):
        self.ai_provider = ai_provider
        self.config = config
        self._processing_semaphore = asyncio.Semaphore(
            self.config.max_concurrent_analyses if self.config.enable_concurrent_analysis else 1
        )
    
    async def analyze_media(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Analyze media and provide AI rating and analysis"""
        try:
            async with self._processing_semaphore:
                # Check processing time limit
                if self.config.max_processing_time > 0:
                    analysis_result = await asyncio.wait_for(
                        self.ai_provider.analyze_media(media_url, media_type),
                        timeout=self.config.max_processing_time
                    )
                else:
                    analysis_result = await self.ai_provider.analyze_media(media_url, media_type)
                
                # Apply confidence threshold filtering
                if analysis_result.get("confidence_score", 0) < self.config.confidence_threshold:
                    logger.warning(f"Low confidence analysis for {media_url}: {analysis_result.get('confidence_score')}")
                
                return analysis_result
                
        except asyncio.TimeoutError:
            logger.error(f"AI analysis timeout for {media_url} after {self.config.max_processing_time}s")
            raise TimeoutError(f"AI analysis timed out after {self.config.max_processing_time} seconds")
        except Exception as e:
            logger.error(f"Error analyzing media {media_url}: {e}")
            raise
    
    async def analyze_multiple_media(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple media files concurrently"""
        try:
            if not self.config.enable_concurrent_analysis:
                # Fall back to sequential processing
                return await self._analyze_media_sequential(media_list)
            
            # Process media concurrently with semaphore control
            async def analyze_single_media(media: Dict[str, Any]) -> Dict[str, Any]:
                try:
                    analysis = await self.analyze_media(media["url"], media["type"])
                    return {
                        "media_id": media["id"],
                        "analysis": analysis,
                        "status": "success"
                    }
                except Exception as e:
                    logger.error(f"Error analyzing media {media.get('id', 'unknown')}: {e}")
                    return {
                        "media_id": media.get("id", "unknown"),
                        "error": str(e),
                        "status": "failed"
                    }
            
            # Create tasks for concurrent execution
            tasks = [analyze_single_media(media) for media in media_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions from gather
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Task {i} failed: {result}")
                    processed_results.append({
                        "media_id": media_list[i].get("id", "unknown"),
                        "error": str(result),
                        "status": "failed"
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error analyzing multiple media: {e}")
            raise
    
    async def _analyze_media_sequential(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback sequential processing for multiple media"""
        results = []
        for media in media_list:
            try:
                analysis = await self.analyze_media(media["url"], media["type"])
                results.append({
                    "media_id": media["id"],
                    "analysis": analysis,
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error analyzing media {media.get('id', 'unknown')}: {e}")
                results.append({
                    "media_id": media.get("id", "unknown"),
                    "error": str(e),
                    "status": "failed"
                })
        
        return results
    
    async def detect_sport(self, media_url: str, media_type: str) -> str:
        """Detect the sport being played in the media"""
        try:
            if not self.config.auto_detect_sport:
                logger.info("Sport auto-detection disabled")
                return "unknown"
            
            sport = await self.ai_provider.detect_sport(media_url, media_type)
            
            # Validate detected sport against supported sports
            if sport not in self.config.supported_sports:
                logger.warning(f"Detected unsupported sport: {sport}")
                return "unknown"
            
            return sport
            
        except Exception as e:
            logger.error(f"Error detecting sport: {e}")
            return "unknown"
    
    async def get_analysis_summary(self, media_id: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of analysis results"""
        try:
            summary = {
                "media_id": media_id,
                "analysis_timestamp": analysis_result.get("analysis_timestamp"),
                "overall_rating": analysis_result.get("rating"),
                "confidence_score": analysis_result.get("confidence_score"),
                "detected_sport": analysis_result.get("detected_sport", "unknown"),
                "ai_provider": analysis_result.get("provider", "unknown"),
                "key_metrics": {},
                "recommendations": []
            }
            
            # Extract key metrics
            detailed_analysis = analysis_result.get("detailed_analysis", {})
            if detailed_analysis:
                summary["key_metrics"]["technical_skills"] = detailed_analysis.get("technical_skills", 0)
                summary["key_metrics"]["physical_attributes"] = detailed_analysis.get("physical_attributes", 0)
                summary["key_metrics"]["game_intelligence"] = detailed_analysis.get("game_intelligence", 0)
            
            # Generate recommendations based on analysis
            rating = analysis_result.get("rating", "unknown")
            if rating == "needs_improvement":
                summary["recommendations"].append("Focus on fundamental skills development")
                summary["recommendations"].append("Consider additional training programs")
            elif rating == "developing":
                summary["recommendations"].append("Continue skill refinement")
                summary["recommendations"].append("Work on consistency")
            elif rating == "good":
                summary["recommendations"].append("Maintain current performance level")
                summary["recommendations"].append("Focus on advanced techniques")
            elif rating in ["excellent", "exceptional"]:
                summary["recommendations"].append("Excellent performance - maintain standards")
                summary["recommendations"].append("Consider mentoring opportunities")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating analysis summary: {e}")
            raise
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and configuration"""
        return {
            "status": "operational",
            "ai_provider": self.ai_provider.get_provider_info(),
            "confidence_threshold": self.config.confidence_threshold,
            "max_processing_time": self.config.max_processing_time,
            "concurrent_analysis_enabled": self.config.enable_concurrent_analysis,
            "max_concurrent_analyses": self.config.max_concurrent_analyses,
            "sport_detection_enabled": self.config.auto_detect_sport,
            "supported_sports": self.config.supported_sports,
            "timestamp": datetime.utcnow().isoformat()
        } 