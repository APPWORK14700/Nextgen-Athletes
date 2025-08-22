"""
Configuration file for AI service
"""
from typing import Dict, Any, Optional
import os
from dataclasses import dataclass
from enum import Enum

class AIModelProvider(Enum):
    """Supported AI model providers"""
    OPENAI = "openai"
    GOOGLE = "google"
    AZURE = "azure"
    CUSTOM = "custom"
    MOCK = "mock"  # For development/testing

@dataclass
class AIConfig:
    """AI service configuration"""
    # Model configuration
    model_provider: AIModelProvider
    model_name: str
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    
    # Analysis settings
    confidence_threshold: float = 0.7
    max_processing_time: int = 30  # seconds
    enable_concurrent_analysis: bool = True
    max_concurrent_analyses: int = 10
    
    # Content validation
    enable_content_moderation: bool = True
    moderation_provider: str = "default"
    moderation_threshold: float = 0.8
    
    # Metadata extraction
    enable_metadata_extraction: bool = True
    extract_technical_details: bool = True
    
    # Sport detection
    supported_sports: list = None
    auto_detect_sport: bool = True
    
    # Performance settings
    cache_results: bool = True
    cache_ttl_hours: int = 24
    
    # Development settings
    enable_mock_mode: bool = False
    mock_delay_range: tuple = (1, 3)  # seconds
    
    def __post_init__(self):
        if self.supported_sports is None:
            self.supported_sports = [
                "soccer", "basketball", "football", "baseball", "tennis",
                "volleyball", "hockey", "rugby", "cricket", "athletics"
            ]

def get_ai_config() -> AIConfig:
    """Get AI service configuration from environment variables with defaults"""
    
    # Determine provider from environment
    provider_str = os.getenv('AI_MODEL_PROVIDER', 'mock').lower()
    try:
        provider = AIModelProvider(provider_str)
    except ValueError:
        provider = AIModelProvider.MOCK
    
    # Check if we should enable mock mode
    enable_mock = (
        provider == AIModelProvider.MOCK or 
        os.getenv('AI_ENABLE_MOCK', 'false').lower() == 'true' or
        not os.getenv('AI_API_KEY')
    )
    
    if enable_mock:
        provider = AIModelProvider.MOCK
    
    config = AIConfig(
        model_provider=provider,
        model_name=os.getenv('AI_MODEL_NAME', 'gpt-4-vision-preview'),
        api_key=os.getenv('AI_API_KEY'),
        api_base_url=os.getenv('AI_API_BASE_URL'),
        
        confidence_threshold=float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7')),
        max_processing_time=int(os.getenv('AI_MAX_PROCESSING_TIME', '30')),
        enable_concurrent_analysis=os.getenv('AI_ENABLE_CONCURRENT', 'true').lower() == 'true',
        max_concurrent_analyses=int(os.getenv('AI_MAX_CONCURRENT', '10')),
        
        enable_content_moderation=os.getenv('AI_ENABLE_MODERATION', 'true').lower() == 'true',
        moderation_provider=os.getenv('AI_MODERATION_PROVIDER', 'default'),
        moderation_threshold=float(os.getenv('AI_MODERATION_THRESHOLD', '0.8')),
        
        enable_metadata_extraction=os.getenv('AI_ENABLE_METADATA', 'true').lower() == 'true',
        extract_technical_details=os.getenv('AI_EXTRACT_TECHNICAL', 'true').lower() == 'true',
        
        auto_detect_sport=os.getenv('AI_AUTO_DETECT_SPORT', 'true').lower() == 'true',
        
        cache_results=os.getenv('AI_CACHE_RESULTS', 'true').lower() == 'true',
        cache_ttl_hours=int(os.getenv('AI_CACHE_TTL_HOURS', '24')),
        
        enable_mock_mode=enable_mock,
        mock_delay_range=(
            int(os.getenv('AI_MOCK_MIN_DELAY', '1')),
            int(os.getenv('AI_MOCK_MAX_DELAY', '3'))
        )
    )
    
    return config

# Environment-specific configurations
def get_ai_config_for_environment(environment: str = None) -> AIConfig:
    """Get AI configuration for specific environment"""
    if not environment:
        environment = os.getenv('ENVIRONMENT', 'development').lower()
    
    # Override environment variables for specific environments
    if environment in ['development', 'dev']:
        os.environ.setdefault('AI_ENABLE_MOCK', 'true')
        os.environ.setdefault('AI_LOG_LEVEL', 'DEBUG')
    elif environment in ['testing', 'test']:
        os.environ.setdefault('AI_ENABLE_MOCK', 'true')
        os.environ.setdefault('AI_MOCK_MIN_DELAY', '0')
        os.environ.setdefault('AI_MOCK_MAX_DELAY', '1')
    elif environment in ['production', 'prod']:
        os.environ.setdefault('AI_ENABLE_MOCK', 'false')
        os.environ.setdefault('AI_LOG_LEVEL', 'WARNING')
    
    return get_ai_config()

# Default configuration
DEFAULT_AI_CONFIG = get_ai_config() 