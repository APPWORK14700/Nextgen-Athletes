from typing import Optional, Dict, Any, List, TypedDict
import logging
from datetime import datetime, timezone

from ..config.ai_config import get_ai_config, AIConfig
from ..ai.providers import create_ai_provider
from ..ai.services import MediaAnalysisService, ContentModerationService, MetadataExtractionService

logger = logging.getLogger(__name__)


class MediaAnalysisResult(TypedDict):
    """Type definition for media analysis results"""
    confidence_score: float
    sport_detected: Optional[str]
    technical_rating: Optional[float]
    analysis_summary: str
    media_url: str
    media_type: str
    timestamp: str


class ContentValidationResult(TypedDict):
    """Type definition for content validation results"""
    is_appropriate: bool
    confidence_score: float
    moderation_notes: Optional[str]
    media_url: str
    media_type: str
    timestamp: str


class MetadataExtractionResult(TypedDict):
    """Type definition for metadata extraction results"""
    metadata: Dict[str, Any]
    confidence_score: float
    media_url: str
    media_type: str
    timestamp: str


class ServiceStatusResult(TypedDict):
    """Type definition for service status results"""
    status: str
    ai_provider: Dict[str, Any]
    services: Dict[str, Any]
    config: Dict[str, Any]
    timestamp: str
    error: Optional[str]


class AIService:
    """AI service for analyzing athlete media and providing ratings"""
    
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or get_ai_config()
        # Create a proper config dict instead of accessing __dict__
        config_dict = {
            'model_provider': self.config.model_provider.value,
            'model_name': self.config.model_name,
            'api_key': self.config.api_key,
            'api_base_url': self.config.api_base_url,
            'confidence_threshold': self.config.confidence_threshold,
            'max_processing_time': self.config.max_processing_time,
            'enable_concurrent_analysis': self.config.enable_concurrent_analysis,
            'max_concurrent_analyses': self.config.max_concurrent_analyses,
            'enable_content_moderation': self.config.enable_content_moderation,
            'moderation_threshold': self.config.moderation_threshold,
            'enable_metadata_extraction': self.config.enable_metadata_extraction,
            'extract_technical_details': self.config.extract_technical_details,
            'auto_detect_sport': self.config.auto_detect_sport,
            'supported_sports': self.config.supported_sports,
            'cache_results': self.config.cache_results,
            'cache_ttl_hours': self.config.cache_ttl_hours,
            'enable_mock_mode': self.config.enable_mock_mode,
        }
        self.ai_provider = create_ai_provider(config_dict)
        
        # Initialize specialized services
        self.analysis_service = MediaAnalysisService(self.ai_provider, self.config)
        self.moderation_service = ContentModerationService(self.ai_provider, self.config)
        self.extraction_service = MetadataExtractionService(self.ai_provider, self.config)
    
    def _validate_media_input(self, media_url: str, media_type: str) -> None:
        """Validate media input parameters"""
        if not media_url or not isinstance(media_url, str):
            raise ValueError("media_url must be a non-empty string")
        if not media_type or not isinstance(media_type, str):
            raise ValueError("media_type must be a non-empty string")
        if not media_url.startswith(('http://', 'https://', 'file://')):
            raise ValueError("media_url must be a valid URL or file path")

    def _validate_media_list(self, media_list: List[Dict[str, Any]]) -> None:
        """Validate media list input"""
        if not isinstance(media_list, list):
            raise ValueError("media_list must be a list")
        if not media_list:
            raise ValueError("media_list cannot be empty")
        for media in media_list:
            if not isinstance(media, dict):
                raise ValueError("Each media item must be a dictionary")
            if 'url' not in media or 'type' not in media:
                raise ValueError("Each media item must contain 'url' and 'type' keys")

    async def analyze_media(self, media_url: str, media_type: str) -> MediaAnalysisResult:
        """Analyze media and provide AI rating and analysis"""
        self._validate_media_input(media_url, media_type)
        try:
            return await self.analysis_service.analyze_media(media_url, media_type)
        except Exception as e:
            logger.error(f"Error analyzing media {media_url}: {e}")
            raise
    
    async def analyze_multiple_media(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze multiple media files concurrently"""
        self._validate_media_list(media_list)
        try:
            return await self.analysis_service.analyze_multiple_media(media_list)
        except Exception as e:
            logger.error(f"Error analyzing multiple media: {e}")
            raise
    
    async def validate_media_content(self, media_url: str, media_type: str) -> ContentValidationResult:
        """Validate media content for appropriateness"""
        self._validate_media_input(media_url, media_type)
        try:
            return await self.moderation_service.validate_content(media_url, media_type)
        except Exception as e:
            logger.error(f"Error validating media content {media_url}: {e}")
            raise
    
    async def extract_metadata(self, media_url: str, media_type: str) -> MetadataExtractionResult:
        """Extract metadata from media"""
        self._validate_media_input(media_url, media_type)
        try:
            return await self.extraction_service.extract_metadata(media_url, media_type)
        except Exception as e:
            logger.error(f"Error extracting metadata from {media_url}: {e}")
            raise
    
    async def detect_sport(self, media_url: str, media_type: str) -> str:
        """Detect the sport being played in the media"""
        self._validate_media_input(media_url, media_type)
        try:
            return await self.analysis_service.detect_sport(media_url, media_type)
        except Exception as e:
            logger.error(f"Error detecting sport for {media_url}: {e}")
            raise
    
    async def get_analysis_summary(self, media_id: str, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of analysis results"""
        if not media_id or not isinstance(media_id, str):
            raise ValueError("media_id must be a non-empty string")
        if not isinstance(analysis_result, dict):
            raise ValueError("analysis_result must be a dictionary")
        try:
            return await self.analysis_service.get_analysis_summary(media_id, analysis_result)
        except Exception as e:
            logger.error(f"Error generating analysis summary for {media_id}: {e}")
            raise
    
    # Batch operations for multiple media
    async def batch_validate_content(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate multiple media files for content appropriateness"""
        self._validate_media_list(media_list)
        try:
            return await self.moderation_service.batch_validate_content(media_list)
        except Exception as e:
            logger.error(f"Error batch validating content: {e}")
            raise
    
    async def batch_extract_metadata(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract metadata from multiple media files"""
        self._validate_media_list(media_list)
        try:
            return await self.extraction_service.batch_extract_metadata(media_list)
        except Exception as e:
            logger.error(f"Error batch extracting metadata: {e}")
            raise
    
    # Statistics and reporting
    def get_moderation_stats(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics from content moderation results"""
        if not isinstance(validation_results, list):
            raise ValueError("validation_results must be a list")
        try:
            return self.moderation_service.get_moderation_stats(validation_results)
        except Exception as e:
            logger.error(f"Error getting moderation stats: {e}")
            raise
    
    def get_metadata_summary(self, metadata_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics from metadata extraction results"""
        if not isinstance(metadata_results, list):
            raise ValueError("metadata_results must be a list")
        try:
            return self.extraction_service.get_metadata_summary(metadata_results)
        except Exception as e:
            logger.error(f"Error getting metadata summary: {e}")
            raise
    
    def get_service_status(self) -> ServiceStatusResult:
        """Get current service status and configuration"""
        try:
            return {
                "status": "operational",
                "ai_provider": self.ai_provider.get_provider_info(),
                "services": {
                    "analysis": self.analysis_service.get_service_status(),
                    "moderation": self.moderation_service.get_service_status(),
                    "extraction": self.extraction_service.get_service_status()
                },
                "config": {
                    "confidence_threshold": self.config.confidence_threshold,
                    "max_processing_time": self.config.max_processing_time,
                    "enable_concurrent_analysis": self.config.enable_concurrent_analysis,
                    "max_concurrent_analyses": self.config.max_concurrent_analyses,
                    "enable_content_moderation": self.config.enable_content_moderation,
                    "moderation_threshold": self.config.moderation_threshold,
                    "enable_metadata_extraction": self.config.enable_metadata_extraction,
                    "extract_technical_details": self.config.extract_technical_details,
                    "auto_detect_sport": self.config.auto_detect_sport,
                    "supported_sports": self.config.supported_sports,
                    "cache_results": self.config.cache_results,
                    "cache_ttl_hours": self.config.cache_ttl_hours,
                    "mock_mode": self.config.enable_mock_mode
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def is_healthy(self) -> bool:
        """Check if the service is healthy and ready to process requests"""
        try:
            # Check if AI provider is available
            provider_info = self.ai_provider.get_provider_info()
            if not provider_info.get('available', False):
                return False
            
            # Check if all services are operational
            status = self.get_service_status()
            return status['status'] == 'operational'
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a concise health summary"""
        try:
            is_healthy = self.is_healthy()
            return {
                "healthy": is_healthy,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ai_provider_available": self.ai_provider.get_provider_info().get('available', False),
                "services_operational": is_healthy
            }
        except Exception as e:
            logger.error(f"Error getting health summary: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            } 