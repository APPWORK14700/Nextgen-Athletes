import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import ValidationError, AuthorizationError


class TestOpportunitiesAPI:
    """Test cases for opportunities API endpoints"""
    
    def test_create_opportunity_success(self, client, mock_scout_user):
        """Test creating opportunity successfully"""
        opportunity_data = {
            "title": "NFL Quarterback Opportunity",
            "description": "Looking for talented quarterbacks",
            "sport": "football",
            "position": "quarterback",
            "location": "New York, NY"
        }
        
        with patch('app.api.v1.opportunities.require_verified_scout', return_value=mock_scout_user):
            with patch('app.api.v1.opportunities.opportunity_service.create_opportunity') as mock_create:
                mock_create.return_value = {
                    "id": "opp123",
                    "title": "NFL Quarterback Opportunity",
                    "scout_id": "scout_user_id"
                }
                
                response = client.post("/api/v1/opportunities/", json=opportunity_data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["title"] == "NFL Quarterback Opportunity"
    
    def test_search_opportunities_success(self, client, mock_current_user):
        """Test searching opportunities successfully"""
        with patch('app.api.v1.opportunities.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.opportunities.opportunity_service.search_opportunities') as mock_search:
                mock_search.return_value = {
                    "opportunities": [
                        {"id": "opp1", "title": "NFL QB", "sport": "football"},
                        {"id": "opp2", "title": "NBA PG", "sport": "basketball"}
                    ],
                    "total": 2,
                    "page": 1,
                    "limit": 20
                }
                
                response = client.get("/api/v1/opportunities/?sport=football")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["opportunities"]) == 2
                assert data["total"] == 2
    
    def test_apply_for_opportunity_success(self, client, mock_athlete_user):
        """Test applying for opportunity successfully"""
        application_data = {
            "cover_letter": "I'm interested in this opportunity",
            "resume_url": "https://example.com/resume.pdf"
        }
        
        with patch('app.api.v1.opportunities.require_athlete_role', return_value=mock_athlete_user):
            with patch('app.api.v1.opportunities.opportunity_service.apply_for_opportunity') as mock_apply:
                mock_apply.return_value = {
                    "id": "app123",
                    "opportunity_id": "opp123",
                    "athlete_id": "athlete_user_id",
                    "status": "pending"
                }
                
                response = client.post("/api/v1/opportunities/opp123/apply", json=application_data)
                
                assert response.status_code == 201
                data = response.json()
                assert data["opportunity_id"] == "opp123"
                assert data["athlete_id"] == "athlete_user_id"
    
    def test_get_opportunity_success(self, client, mock_current_user):
        """Test getting opportunity details successfully"""
        with patch('app.api.v1.opportunities.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.opportunities.opportunity_service.get_opportunity_by_id') as mock_get:
                mock_get.return_value = {
                    "id": "opp123",
                    "title": "NFL Quarterback Position",
                    "description": "Seeking talented quarterback",
                    "sport": "football"
                }
                
                response = client.get("/api/v1/opportunities/opp123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["title"] == "NFL Quarterback Position"
                assert data["sport"] == "football" 