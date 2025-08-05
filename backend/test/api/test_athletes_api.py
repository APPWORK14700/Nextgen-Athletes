import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import ValidationError, AuthorizationError


class TestAthletesAPI:
    """Test cases for athletes API endpoints"""
    
    def test_create_athlete_profile_success(self, client, mock_athlete_user):
        """Test creating athlete profile successfully"""
        profile_data = {
            "first_name": "John",
            "last_name": "Doe",
            "sport": "football",
            "position": "quarterback",
            "age": 22,
            "height": 185,
            "weight": 85
        }
        
        with patch('app.api.v1.athletes.get_current_user', return_value=mock_athlete_user):
            with patch('app.api.v1.athletes.athlete_service.create_profile') as mock_create:
                mock_create.return_value = {
                    "user_id": "athlete_user_id",
                    "first_name": "John",
                    "last_name": "Doe",
                    "sport": "football"
                }
                
                response = client.post("/api/v1/athletes/profile", json=profile_data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["first_name"] == "John"
                assert data["sport"] == "football"
    
    def test_create_athlete_profile_wrong_role(self, client, mock_scout_user):
        """Test creating athlete profile with wrong user role"""
        profile_data = {
            "first_name": "John",
            "last_name": "Doe",
            "sport": "football"
        }
        
        with patch('app.api.v1.athletes.get_current_user', return_value=mock_scout_user):
            response = client.post("/api/v1/athletes/profile", json=profile_data)
            
            assert response.status_code == 400
            assert "Only users with athlete role" in response.json()["detail"]
    
    def test_search_athletes_success(self, client, mock_current_user):
        """Test searching athletes successfully"""
        with patch('app.api.v1.athletes.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.athletes.athlete_service.search_athletes') as mock_search:
                mock_search.return_value = {
                    "athletes": [
                        {"user_id": "athlete1", "first_name": "John", "sport": "football"},
                        {"user_id": "athlete2", "first_name": "Jane", "sport": "basketball"}
                    ],
                    "total": 2,
                    "page": 1,
                    "limit": 20
                }
                
                response = client.get("/api/v1/athletes/search?sport=football")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["athletes"]) == 2
                assert data["total"] == 2
    
    def test_get_athlete_stats_success(self, client, mock_athlete_user):
        """Test getting athlete stats successfully"""
        with patch('app.api.v1.athletes.require_athlete_role', return_value=mock_athlete_user):
            with patch('app.api.v1.athletes.athlete_service.get_stats') as mock_stats:
                mock_stats.return_value = {
                    "games_played": 25,
                    "points": 150,
                    "assists": 45
                }
                
                response = client.get("/api/v1/athletes/stats")
                
                assert response.status_code == 200
                data = response.json()
                assert data["games_played"] == 25
                assert data["points"] == 150
    
    def test_update_athlete_profile_success(self, client, mock_athlete_user):
        """Test updating athlete profile successfully"""
        update_data = {"position": "running_back", "weight": 90}
        
        with patch('app.api.v1.athletes.require_athlete_role', return_value=mock_athlete_user):
            with patch('app.api.v1.athletes.athlete_service.update_profile') as mock_update:
                mock_update.return_value = {
                    "user_id": "athlete_user_id",
                    "position": "running_back",
                    "weight": 90
                }
                
                response = client.put("/api/v1/athletes/profile", json=update_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["position"] == "running_back"
                assert data["weight"] == 90
    
    def test_get_athlete_recommendations_success(self, client, mock_athlete_user):
        """Test getting athlete recommendations successfully"""
        with patch('app.api.v1.athletes.require_athlete_role', return_value=mock_athlete_user):
            with patch('app.api.v1.athletes.athlete_service.get_recommendations') as mock_recs:
                mock_recs.return_value = [
                    {"id": "opp1", "title": "NFL Tryout", "match_score": 0.95},
                    {"id": "opp2", "title": "College Scholarship", "match_score": 0.87}
                ]
                
                response = client.get("/api/v1/athletes/recommendations")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert data[0]["title"] == "NFL Tryout"
    
    def test_submit_verification_success(self, client, mock_athlete_user):
        """Test submitting verification successfully"""
        verification_data = {
            "document_type": "student_id",
            "document_url": "https://example.com/id.jpg"
        }
        
        with patch('app.api.v1.athletes.require_athlete_role', return_value=mock_athlete_user):
            with patch('app.api.v1.athletes.athlete_service.submit_verification') as mock_verify:
                mock_verify.return_value = {
                    "id": "verification123",
                    "status": "pending"
                }
                
                response = client.post("/api/v1/athletes/verification", json=verification_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "pending" 