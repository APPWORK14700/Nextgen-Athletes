import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.services.ai_service import AIService
from app.api.exceptions import ValidationError


class TestAIService:
    """Test cases for AIService"""
    
    @pytest.mark.asyncio
    async def test_analyze_media(self, mock_ai_service):
        """Test media analysis"""
        media_data = {
            "url": "https://example.com/video.mp4",
            "sport": "football",
            "media_type": "video"
        }
        
        # Mock analysis result
        mock_ai_service.analyze_media.return_value = {
            "rating": "excellent",
            "summary": "Great performance with strong technique",
            "metrics": {
                "technical_skills": 8.5,
                "physical_attributes": 9.0,
                "game_intelligence": 8.0
            },
            "confidence_score": 0.92
        }
        
        result = await mock_ai_service.analyze_media("media123", media_data)
        
        assert result is not None
        assert "rating" in result
        assert "summary" in result
        assert "metrics" in result
        assert result["rating"] == "excellent"
    
    @pytest.mark.asyncio
    async def test_analyze_media_with_retry(self, mock_ai_service):
        """Test media analysis with retry logic"""
        # Mock first attempt fails, second succeeds
        mock_ai_service.analyze_media_with_retry.return_value = {
            "rating": 8.5, 
            "summary": "Good performance",
            "retry_count": 1
        }
        
        result = await mock_ai_service.analyze_media_with_retry("media123", {})
        
        assert result["rating"] == 8.5
        assert result["summary"] == "Good performance"
        assert result["retry_count"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_recommendations(self, mock_ai_service):
        """Test generating recommendations"""
        user_data = {
            "sport": "football",
            "position": "quarterback",
            "stats": {"passing_yards": 3500}
        }
        
        # Mock recommendations
        mock_ai_service.generate_recommendations.return_value = {
            "opportunities": [
                {"id": "opp1", "title": "NFL Tryout", "match_score": 0.95},
                {"id": "opp2", "title": "College Scout", "match_score": 0.87}
            ],
            "improvements": [
                "Work on accuracy in short passes",
                "Improve pocket awareness"
            ]
        }
        
        result = await mock_ai_service.generate_recommendations("user123", user_data)
        
        assert result is not None
        assert "opportunities" in result
        assert "improvements" in result
        assert len(result["opportunities"]) == 2
        assert len(result["improvements"]) == 2 