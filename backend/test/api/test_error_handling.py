import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)


class TestErrorHandling:
    """Test cases for error handling across API endpoints"""
    
    def test_validation_error(self, client):
        """Test validation error handling"""
        invalid_data = {"email": "invalid-email"}
        
        response = client.post("/api/v1/auth/register", json=invalid_data)
        
        assert response.status_code == 422
        assert "validation" in response.json()["detail"][0]["type"]
    
    def test_authentication_error(self, client):
        """Test authentication error handling"""
        with patch('app.api.v1.auth.auth_service.login_user') as mock_login:
            mock_login.side_effect = AuthenticationError("Invalid credentials")
            
            response = client.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "wrong_password"
            })
            
            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]
    
    def test_authorization_error(self, client, mock_athlete_user):
        """Test authorization error handling"""
        with patch('app.api.v1.admin.require_admin_role') as mock_admin:
            mock_admin.side_effect = AuthorizationError("Admin access required")
            
            response = client.get("/api/v1/admin/users")
            
            assert response.status_code == 403
            assert "Admin access required" in response.json()["detail"]
    
    def test_resource_not_found_error(self, client, mock_current_user):
        """Test resource not found error handling"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            with patch('app.api.v1.users.user_service.get_user_profile') as mock_get:
                mock_get.side_effect = ResourceNotFoundError("User profile not found")
                
                response = client.get("/api/v1/users/profile")
                
                assert response.status_code == 404
                assert "User profile not found" in response.json()["detail"]
    
    def test_rate_limit_error(self, client):
        """Test rate limit error handling"""
        with patch('app.api.v1.auth.auth_service.register_user') as mock_register:
            mock_register.side_effect = RateLimitError("Rate limit exceeded")
            
            response = client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "password123"
            })
            
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_internal_server_error(self, client):
        """Test internal server error handling"""
        with patch('app.api.v1.auth.auth_service.register_user') as mock_register:
            mock_register.side_effect = Exception("Unexpected error")
            
            response = client.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "password123",
                "first_name": "Test",
                "last_name": "User",
                "role": "athlete"
            })
            
            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
    
    def test_missing_authorization_header(self, client):
        """Test missing authorization header"""
        response = client.get("/api/v1/users/profile")
        
        assert response.status_code == 401
    
    def test_invalid_json_body(self, client):
        """Test invalid JSON body handling"""
        response = client.post(
            "/api/v1/auth/login", 
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self, client):
        """Test missing required fields in request"""
        incomplete_data = {"email": "test@example.com"}  # Missing password
        
        response = client.post("/api/v1/auth/login", json=incomplete_data)
        
        assert response.status_code == 422
    
    def test_invalid_uuid_parameter(self, client, mock_current_user):
        """Test invalid UUID parameter handling"""
        with patch('app.api.v1.users.get_current_user', return_value=mock_current_user):
            response = client.get("/api/v1/users/invalid-uuid/profile")
            
            # Should handle invalid UUID gracefully
            assert response.status_code in [400, 422, 404] 