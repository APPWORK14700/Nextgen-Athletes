"""
Abstract base class for AI providers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class AIProvider(ABC):
    """Abstract base class for AI service providers"""
    
    @abstractmethod
    async def analyze_media(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Analyze media and return analysis results"""
        pass
    
    @abstractmethod
    async def validate_content(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Validate media content for appropriateness"""
        pass
    
    @abstractmethod
    async def extract_metadata(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Extract metadata from media"""
        pass
    
    @abstractmethod
    async def detect_sport(self, media_url: str, media_type: str) -> str:
        """Detect the sport being played in the media"""
        pass
    
    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this AI provider"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available for use"""
        pass 