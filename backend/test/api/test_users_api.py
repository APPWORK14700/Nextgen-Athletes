import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import ValidationError, ResourceNotFoundError


class TestUsersAPI:
    """Test cases for users API endpoints"""
    
    def test_get_user_profile_success(self, client, mock_current_user):
        """Test getting user profile successfully"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.get_user_profile') as mock_get_profile:
                mock_get_profile.return_value = {
                    "user_id": "user123",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john@example.com"
                }
                
                response = client.get("/api/v1/users/profile")
                
                assert response.status_code == 200
                data = response.json()
                assert data["first_name"] == "John"
                assert data["last_name"] == "Doe"
    
    def test_get_user_profile_unauthorized(self, client):
        """Test getting user profile without authentication"""
        response = client.get("/api/v1/users/profile")
        
        assert response.status_code == 401
    
    def test_update_user_profile_success(self, client, mock_current_user):
        """Test updating user profile successfully"""
        update_data = {
            "first_name": "Jane",
            "last_name": "Smith"
        }
        
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.update_user_profile') as mock_update:
                mock_update.return_value = {
                    "user_id": "user123",
                    "first_name": "Jane",
                    "last_name": "Smith"
                }
                
                response = client.put("/api/v1/users/profile", json=update_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["first_name"] == "Jane"
                assert data["last_name"] == "Smith"
    
    def test_delete_user_profile_success(self, client, mock_current_user):
        """Test deleting user profile successfully"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.delete_user_profile') as mock_delete:
                mock_delete.return_value = {"message": "Profile deleted successfully"}
                
                response = client.delete("/api/v1/users/profile")
                
                assert response.status_code == 200
                assert response.json()["message"] == "Profile deleted successfully"
    
    def test_get_user_settings_success(self, client, mock_current_user):
        """Test getting user settings successfully"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.get_user_settings') as mock_get_settings:
                mock_get_settings.return_value = {
                    "notifications_enabled": True,
                    "privacy_level": "public"
                }
                
                response = client.get("/api/v1/users/settings")
                
                assert response.status_code == 200
                data = response.json()
                assert data["notifications_enabled"] is True
                assert data["privacy_level"] == "public"
    
    def test_update_user_settings_success(self, client, mock_current_user):
        """Test updating user settings successfully"""
        settings_data = {
            "notifications_enabled": False,
            "privacy_level": "private"
        }
        
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.update_user_settings') as mock_update:
                mock_update.return_value = settings_data
                
                response = client.put("/api/v1/users/settings", json=settings_data)
                
                assert response.status_code == 200
                data = response.json()
                assert data["notifications_enabled"] is False
                assert data["privacy_level"] == "private"
    
    def test_block_user_success(self, client, mock_current_user):
        """Test blocking a user successfully"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.block_user') as mock_block:
                mock_block.return_value = {"message": "User blocked successfully"}
                
                response = client.post("/api/v1/users/user456/block", 
                                     data={"reason": "spam"})
                
                assert response.status_code == 200
                assert response.json()["message"] == "User blocked successfully"
    
    def test_report_user_success(self, client, mock_current_user):
        """Test reporting a user successfully"""
        report_data = {
            "reason": "harassment",
            "description": "Inappropriate messages"
        }
        
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.report_user') as mock_report:
                mock_report.return_value = {"message": "User reported successfully"}
                
                response = client.post("/api/v1/users/user456/report", json=report_data)
                
                assert response.status_code == 200
                assert response.json()["message"] == "User reported successfully" 