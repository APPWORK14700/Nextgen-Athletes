import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


class TestMediaAPI:
    """Test cases for media API endpoints"""
    
    def test_upload_media_success(self, client, mock_athlete_user):
        """Test uploading media successfully"""
        with patch('app.api.v1.media.get_current_user', return_value=mock_athlete_user):
            with patch('app.api.v1.media.media_service.upload_media') as mock_upload:
                mock_upload.return_value = {
                    "id": "media123",
                    "title": "Game Highlights",
                    "user_id": "athlete_user_id",
                    "url": "https://example.com/video.mp4"
                }
                
                # Create a mock file
                files = {"file": ("video.mp4", b"fake video content", "video/mp4")}
                data = {
                    "title": "Game Highlights",
                    "description": "Best plays from last season",
                    "tags": "highlights,football"
                }
                
                response = client.post("/api/v1/media/upload", files=files, data=data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["title"] == "Game Highlights"
                assert data["user_id"] == "athlete_user_id"
    
    def test_get_user_media_success(self, client, mock_athlete_user):
        """Test getting user media successfully"""
        with patch('app.api.v1.media.get_current_user', return_value=mock_athlete_user):
            with patch('app.api.v1.media.media_service.get_user_media') as mock_get:
                mock_get.return_value = [
                    {"id": "media1", "title": "Video 1", "user_id": "athlete_user_id"},
                    {"id": "media2", "title": "Video 2", "user_id": "athlete_user_id"}
                ]
                
                response = client.get("/api/v1/media/")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert data[0]["title"] == "Video 1"
    
    def test_trigger_media_analysis_success(self, client, mock_athlete_user):
        """Test triggering media analysis successfully"""
        with patch('app.api.v1.media.get_current_user', return_value=mock_athlete_user):
            with patch('app.api.v1.media.media_service.get_media_by_id') as mock_get_media:
                mock_get_media.return_value = {"user_id": "athlete_user_id", "id": "media123"}
                
                with patch('app.api.v1.media.media_service.trigger_analysis') as mock_trigger:
                    mock_trigger.return_value = {"message": "Analysis triggered successfully"}
                    
                    response = client.post("/api/v1/media/media123/analyze")
                    
                    assert response.status_code == 200
                    assert response.json()["message"] == "Analysis triggered successfully"
    
    def test_get_media_analysis_success(self, client, mock_current_user):
        """Test getting media analysis successfully"""
        with patch('app.api.v1.media.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.media.media_service.get_media_analysis') as mock_analysis:
                mock_analysis.return_value = {
                    "rating": "excellent",
                    "summary": "Great performance",
                    "confidence_score": 0.95
                }
                
                response = client.get("/api/v1/media/media123/analysis")
                
                assert response.status_code == 200
                data = response.json()
                assert data["rating"] == "excellent"
                assert data["confidence_score"] == 0.95
    
    def test_search_media_success(self, client, mock_current_user):
        """Test searching media successfully"""
        with patch('app.api.v1.media.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.media.media_service.search_media') as mock_search:
                mock_search.return_value = {
                    "media": [
                        {"id": "media1", "title": "Football Highlights", "sport": "football"},
                        {"id": "media2", "title": "Training Video", "sport": "football"}
                    ],
                    "total": 2
                }
                
                response = client.get("/api/v1/media/search?sport=football")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["media"]) == 2
                assert data["total"] == 2 