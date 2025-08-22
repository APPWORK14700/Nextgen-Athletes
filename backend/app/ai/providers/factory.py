"""
Factory for creating AI providers
"""
import logging
from typing import Dict, Any

from .base import AIProvider
from .mock import MockAIProvider
from .openai import OpenAIProvider

logger = logging.getLogger(__name__)

def create_ai_provider(config: Dict[str, Any]) -> AIProvider:
    """Factory function to create AI provider based on configuration"""
    provider_type = config.get('model_provider', 'mock')
    
    try:
        if provider_type == 'openai':
            return OpenAIProvider(config)
        elif provider_type == 'mock':
            return MockAIProvider(config)
        else:
            # Default to mock for unsupported providers
            logger.warning(f"Unsupported AI provider '{provider_type}', falling back to mock")
            return MockAIProvider(config)
    except Exception as e:
        logger.error(f"Error creating AI provider '{provider_type}': {e}")
        logger.info("Falling back to mock provider")
        return MockAIProvider(config)

def get_available_providers(config: Dict[str, Any]) -> Dict[str, AIProvider]:
    """Get all available AI providers"""
    providers = {}
    
    # Try to create each provider type
    provider_types = ['mock', 'openai']
    
    for provider_type in provider_types:
        try:
            test_config = config.copy()
            test_config['model_provider'] = provider_type
            provider = create_ai_provider(test_config)
            if provider.is_available():
                providers[provider_type] = provider
        except Exception as e:
            logger.warning(f"Provider '{provider_type}' not available: {e}")
    
    return providers

def get_provider_info(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get information about all available providers"""
    providers = get_available_providers(config)
    
    info = {}
    for name, provider in providers.items():
        info[name] = provider.get_provider_info()
    
    return info 