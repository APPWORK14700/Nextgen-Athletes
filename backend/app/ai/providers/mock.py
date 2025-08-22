"""
Mock AI provider for development and testing
"""
import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, Any

from .base import AIProvider

logger = logging.getLogger(__name__)

class MockAIProvider(AIProvider):
    """Mock AI provider for development and testing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = "Mock AI Provider"
        self.provider_version = "1.0.0"
        
        self.rating_levels = ["exceptional", "excellent", "good", "developing", "needs_improvement"]
        self.sports = [
            "soccer", "basketball", "football", "baseball", "tennis",
            "volleyball", "hockey", "rugby", "cricket", "athletics"
        ]
        
        # Sport-specific metric templates
        self.sport_metrics = {
            "soccer": {
                "dribbling_accuracy": (70, 95),
                "passing_accuracy": (75, 90),
                "shooting_accuracy": (60, 85),
                "tackling_success_rate": (65, 90),
                "speed": (7.0, 9.5),
                "stamina": (7.0, 9.0)
            },
            "basketball": {
                "shooting_percentage": (35, 65),
                "rebounding_rate": (5, 15),
                "assist_rate": (2, 8),
                "steal_rate": (1, 4),
                "block_rate": (0.5, 3),
                "vertical_jump": (20, 40)
            },
            "football": {
                "throwing_accuracy": (65, 90),
                "rushing_yards": (50, 200),
                "tackling_efficiency": (70, 95),
                "speed": (7.5, 9.5),
                "strength": (7.0, 9.5),
                "agility": (6.5, 9.0)
            },
            "baseball": {
                "batting_average": (0.200, 0.350),
                "fielding_percentage": (0.950, 0.995),
                "pitching_velocity": (75, 95),
                "base_running_speed": (7.0, 9.5),
                "arm_strength": (7.0, 9.5)
            },
            "tennis": {
                "serve_accuracy": (65, 90),
                "forehand_power": (7.0, 9.5),
                "backhand_consistency": (6.5, 9.0),
                "court_coverage": (7.0, 9.5),
                "mental_toughness": (6.5, 9.0)
            }
        }
    
    async def analyze_media(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Simulate AI analysis results"""
        # Simulate processing time
        delay_range = self.config.get('mock_delay_range', (1, 3))
        await asyncio.sleep(random.uniform(*delay_range))
        
        # Detect sport (or use media type as fallback)
        sport = await self.detect_sport(media_url, media_type)
        
        # Generate analysis results
        rating = random.choice(self.rating_levels)
        confidence_score = random.uniform(0.7, 0.95)
        
        # Generate detailed analysis scores
        detailed_analysis = {
            "technical_skills": round(random.uniform(6.0, 9.5), 1),
            "physical_attributes": round(random.uniform(6.0, 9.5), 1),
            "game_intelligence": round(random.uniform(6.0, 9.5), 1),
            "consistency": round(random.uniform(6.0, 9.5), 1),
            "potential": round(random.uniform(6.0, 9.5), 1)
        }
        
        # Generate sport-specific metrics
        sport_specific_metrics = self._generate_sport_metrics(sport)
        
        # Generate summary
        summary = self._generate_summary(rating, detailed_analysis, sport)
        
        return {
            "rating": rating,
            "summary": summary,
            "detailed_analysis": detailed_analysis,
            "sport_specific_metrics": sport_specific_metrics,
            "detected_sport": sport,
            "confidence_score": round(confidence_score, 3),
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "provider": self.provider_name
        }
    
    async def validate_content(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Simulate content validation"""
        delay_range = self.config.get('mock_delay_range', (1, 3))
        await asyncio.sleep(random.uniform(*delay_range))
        
        # Simulate validation results (80% appropriate)
        is_appropriate = random.choice([True, True, True, True, False])
        
        validation_result = {
            "is_appropriate": is_appropriate,
            "confidence": round(random.uniform(0.8, 0.99), 3),
            "flags": [],
            "moderation_score": round(random.uniform(0.1, 0.9), 3),
            "validation_timestamp": datetime.utcnow().isoformat(),
            "provider": self.provider_name
        }
        
        if not is_appropriate:
            validation_result["flags"] = ["inappropriate_content"]
            validation_result["moderation_score"] = round(random.uniform(0.6, 0.9), 3)
        
        return validation_result
    
    async def extract_metadata(self, media_url: str, media_type: str) -> Dict[str, Any]:
        """Simulate metadata extraction"""
        delay_range = self.config.get('mock_delay_range', (1, 2))
        await asyncio.sleep(random.uniform(*delay_range))
        
        metadata = {
            "duration": random.randint(10, 300) if media_type in ["video", "reel"] else None,
            "resolution": f"{random.choice([720, 1080, 1440])}p",
            "file_size": random.randint(1024, 10240),  # KB
            "format": media_type,
            "extracted_at": datetime.utcnow().isoformat(),
            "provider": self.provider_name,
            "technical_details": {
                "codec": random.choice(["H.264", "H.265", "AV1"]) if media_type in ["video", "reel"] else None,
                "bitrate": random.randint(1000, 8000) if media_type in ["video", "reel"] else None,
                "fps": random.randint(24, 60) if media_type in ["video", "reel"] else None,
                "color_space": random.choice(["RGB", "YCbCr", "HSV"]) if media_type == "image" else None
            }
        }
        
        return metadata
    
    async def detect_sport(self, media_url: str, media_type: str) -> str:
        """Simulate sport detection"""
        # In a real implementation, this would use computer vision
        # For now, use media type as a hint and random selection
        if media_type == "video":
            # Higher probability for team sports
            return random.choice(["soccer", "basketball", "football", "baseball", "volleyball"])
        elif media_type == "reel":
            # Higher probability for individual sports
            return random.choice(["basketball", "tennis", "athletics", "gymnastics"])
        else:
            # Images could be any sport
            return random.choice(self.sports)
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this AI provider"""
        return {
            "name": self.provider_name,
            "version": self.provider_version,
            "type": "mock",
            "capabilities": [
                "media_analysis",
                "content_validation", 
                "metadata_extraction",
                "sport_detection"
            ],
            "config": self.config
        }
    
    def is_available(self) -> bool:
        """Check if this provider is available for use"""
        return True  # Mock provider is always available
    
    def _generate_sport_metrics(self, sport: str) -> Dict[str, Any]:
        """Generate sport-specific metrics"""
        if sport in self.sport_metrics:
            metrics = {}
            for metric, (min_val, max_val) in self.sport_metrics[sport].items():
                if isinstance(min_val, int):
                    metrics[metric] = random.randint(min_val, max_val)
                else:
                    metrics[metric] = round(random.uniform(min_val, max_val), 1)
            return metrics
        else:
            # Generic metrics for unsupported sports
            return {
                "athletic_presence": round(random.uniform(7.0, 9.5), 1),
                "physical_condition": round(random.uniform(7.0, 9.5), 1),
                "technique_display": round(random.uniform(6.5, 9.0), 1)
            }
    
    def _generate_summary(self, rating: str, detailed_analysis: Dict[str, float], sport: str) -> str:
        """Generate AI summary based on analysis results"""
        technical_score = detailed_analysis.get('technical_skills', 7.0)
        game_intelligence = detailed_analysis.get('game_intelligence', 7.0)
        
        if rating == "exceptional":
            return f"Exceptional {sport} performance with outstanding technical skills ({technical_score}/10) and game intelligence ({game_intelligence}/10). Shows elite-level potential with excellent consistency."
        elif rating == "excellent":
            return f"Excellent {sport} performance demonstrating strong technical abilities ({technical_score}/10) and good game understanding. Shows high potential for development."
        elif rating == "good":
            return f"Good {sport} performance with solid fundamentals. Technical skills ({technical_score}/10) are developing well with room for improvement in consistency."
        elif rating == "developing":
            return f"Developing {sport} player with basic skills in place. Technical abilities ({technical_score}/10) need refinement, but shows potential for growth."
        else:
            return f"Needs improvement in several {sport} areas. Technical skills ({technical_score}/10) require significant development. Focus on fundamentals recommended." 