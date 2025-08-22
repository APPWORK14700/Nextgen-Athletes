"""
Content moderation service using AI providers
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from ..providers.base import AIProvider
from ...config.ai_config import AIConfig

logger = logging.getLogger(__name__)

class ContentModerationService:
    """Service for content moderation using AI providers"""
    
    def __init__(self, ai_provider: AIProvider, config: AIConfig):
        self.ai_provider = ai_provider
        self.config = config
    
    async def validate_content(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Validate media content for appropriateness"""
        try:
            if not self.config.enable_content_moderation:
                logger.info("Content moderation disabled, skipping validation")
                return {
                    "is_appropriate": True,
                    "confidence": 1.0,
                    "flags": [],
                    "moderation_score": 0.0,
                    "validation_timestamp": datetime.utcnow().isoformat(),
                    "ai_provider": "disabled",
                    "note": "Content moderation disabled"
                }
            
            validation_result = await self.ai_provider.validate_content(media_url, media_type)
            
            # Apply moderation threshold
            if validation_result.get("moderation_score", 0) > self.config.moderation_threshold:
                validation_result["is_appropriate"] = False
                if "inappropriate_content" not in validation_result.get("flags", []):
                    validation_result["flags"].append("moderation_threshold_exceeded")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating media content: {e}")
            raise
    
    async def batch_validate_content(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate multiple media files for content appropriateness"""
        try:
            results = []
            for media in media_list:
                try:
                    validation = await self.validate_content(media["url"], media["type"])
                    results.append({
                        "media_id": media["id"],
                        "validation": validation,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"Error validating media {media.get('id', 'unknown')}: {e}")
                    results.append({
                        "media_id": media.get("id", "unknown"),
                        "error": str(e),
                        "status": "failed"
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error batch validating content: {e}")
            raise
    
    def get_moderation_stats(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics from content moderation results"""
        try:
            total = len(validation_results)
            if total == 0:
                return {"total": 0, "appropriate": 0, "inappropriate": 0, "confidence_avg": 0.0}
            
            appropriate = sum(1 for r in validation_results if r.get("validation", {}).get("is_appropriate", True))
            inappropriate = total - appropriate
            
            confidence_scores = [
                r.get("validation", {}).get("confidence", 0.0) 
                for r in validation_results 
                if r.get("status") == "success"
            ]
            confidence_avg = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            return {
                "total": total,
                "appropriate": appropriate,
                "inappropriate": inappropriate,
                "confidence_avg": round(confidence_avg, 3),
                "moderation_rate": round(inappropriate / total * 100, 1) if total > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating moderation stats: {e}")
            return {"error": str(e)}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and configuration"""
        return {
            "status": "operational",
            "ai_provider": self.ai_provider.get_provider_info(),
            "content_moderation_enabled": self.config.enable_content_moderation,
            "moderation_threshold": self.config.moderation_threshold,
            "moderation_provider": self.config.moderation_provider,
            "timestamp": datetime.utcnow().isoformat()
        } 