"""
Metadata extraction service using AI providers
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from ..providers.base import AIProvider
from ...config.ai_config import AIConfig

logger = logging.getLogger(__name__)

class MetadataExtractionService:
    """Service for extracting metadata from media using AI providers"""
    
    def __init__(self, ai_provider: AIProvider, config: AIConfig):
        self.ai_provider = ai_provider
        self.config = config
    
    async def extract_metadata(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Extract metadata from media"""
        try:
            if not self.config.enable_metadata_extraction:
                logger.info("Metadata extraction disabled, returning basic info")
                return {
                    "format": media_type,
                    "extracted_at": datetime.utcnow().isoformat(),
                    "ai_provider": "disabled",
                    "note": "Metadata extraction disabled"
                }
            
            metadata = await self.ai_provider.extract_metadata(media_url, media_type)
            
            # Filter technical details based on configuration
            if not self.config.extract_technical_details:
                metadata.pop("technical_details", None)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise
    
    async def batch_extract_metadata(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract metadata from multiple media files"""
        try:
            results = []
            for media in media_list:
                try:
                    metadata = await self.extract_metadata(media["url"], media["type"])
                    results.append({
                        "media_id": media["id"],
                        "metadata": metadata,
                        "status": "success"
                    })
                except Exception as e:
                    logger.error(f"Error extracting metadata from media {media.get('id', 'unknown')}: {e}")
                    results.append({
                        "media_id": media.get("id", "unknown"),
                        "error": str(e),
                        "status": "failed"
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error batch extracting metadata: {e}")
            raise
    
    def get_metadata_summary(self, metadata_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics from metadata extraction results"""
        try:
            total = len(metadata_results)
            if total == 0:
                return {"total": 0, "successful": 0, "failed": 0, "formats": {}}
            
            successful = sum(1 for r in metadata_results if r.get("status") == "success")
            failed = total - successful
            
            # Count media formats
            formats = {}
            for result in metadata_results:
                if result.get("status") == "success":
                    format_type = result.get("metadata", {}).get("format", "unknown")
                    formats[format_type] = formats.get(format_type, 0) + 1
            
            # Calculate average file sizes
            file_sizes = [
                r.get("metadata", {}).get("file_size", 0)
                for r in metadata_results 
                if r.get("status") == "success" and r.get("metadata", {}).get("file_size")
            ]
            avg_file_size = sum(file_sizes) / len(file_sizes) if file_sizes else 0
            
            return {
                "total": total,
                "successful": successful,
                "failed": failed,
                "success_rate": round(successful / total * 100, 1) if total > 0 else 0.0,
                "formats": formats,
                "avg_file_size_kb": round(avg_file_size, 1) if avg_file_size > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating metadata summary: {e}")
            return {"error": str(e)}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and configuration"""
        return {
            "status": "operational",
            "ai_provider": self.ai_provider.get_provider_info(),
            "metadata_extraction_enabled": self.config.enable_metadata_extraction,
            "extract_technical_details": self.config.extract_technical_details,
            "timestamp": datetime.utcnow().isoformat()
        } 