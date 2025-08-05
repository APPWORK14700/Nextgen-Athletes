import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)


class TestAuthAPI:
    """Test cases for authentication API endpoints"""
    
    def test_register_user_success(self, client):
        """Test successful user registration"""
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "John",
            "last_name": "Doe",
            "role": "athlete"
        }
        
        with patch('app.api.v1.auth.auth_service.register_user') as mock_register:
            mock_register.return_value = {
                "uid": "user123",
                "email": "test@example.com",
                "role": "athlete"
            }
            
            response = client.post("/api/v1/auth/register", json=user_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["uid"] == "user123"
            assert data["email"] == "test@example.com"
    
    def test_register_user_invalid_data(self, client):
        """Test user registration with invalid data"""
        user_data = {
            "email": "invalid-email",
            "password": "123",  # Too short
            "role": "invalid_role"
        }
        
        response = client.post("/api/v1/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_login_user_success(self, client):
        """Test successful user login"""
        login_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        with patch('app.api.v1.auth.auth_service.login_user') as mock_login:
            mock_login.return_value = {
                "access_token": "valid_token",
                "refresh_token": "refresh_token",
                "user": {
                    "uid": "user123",
                    "email": "test@example.com",
                    "role": "athlete"
                }
            }
            
            response = client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
    
    def test_login_user_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        login_data = {
            "email": "test@example.com",
            "password": "wrong_password"
        }
        
        with patch('app.api.v1.auth.auth_service.login_user') as mock_login:
            mock_login.side_effect = AuthenticationError("Invalid credentials")
            
            response = client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]
    
    def test_refresh_token_success(self, client):
        """Test successful token refresh"""
        refresh_data = {"refresh_token": "valid_refresh_token"}
        
        with patch('app.api.v1.auth.auth_service.refresh_token') as mock_refresh:
            mock_refresh.return_value = {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token"
            }
            
            response = client.post("/api/v1/auth/refresh", json=refresh_data)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data
    
    def test_logout_success(self, client):
        """Test successful logout"""
        with patch('app.api.v1.auth.auth_service.logout') as mock_logout:
            mock_logout.return_value = {"message": "Logged out successfully"}
            
            response = client.post("/api/v1/auth/logout")
            
            assert response.status_code == 200
            assert response.json()["message"] == "Logged out successfully"
    
    def test_verify_email_success(self, client):
        """Test successful email verification"""
        verify_data = {"token": "verification_token"}
        
        with patch('app.api.v1.auth.auth_service.verify_email') as mock_verify:
            mock_verify.return_value = {"message": "Email verified successfully"}
            
            response = client.post("/api/v1/auth/verify-email", json=verify_data)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Email verified successfully"
    
    def test_forgot_password_success(self, client):
        """Test successful forgot password request"""
        forgot_data = {"email": "test@example.com"}
        
        with patch('app.api.v1.auth.auth_service.forgot_password') as mock_forgot:
            mock_forgot.return_value = {"message": "Password reset email sent"}
            
            response = client.post("/api/v1/auth/forgot-password", json=forgot_data)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Password reset email sent"
    
    def test_reset_password_success(self, client):
        """Test successful password reset"""
        reset_data = {
            "token": "reset_token",
            "new_password": "new_password123"
        }
        
        with patch('app.api.v1.auth.auth_service.reset_password') as mock_reset:
            mock_reset.return_value = {"message": "Password reset successfully"}
            
            response = client.post("/api/v1/auth/reset-password", json=reset_data)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Password reset successfully"
    
    def test_change_password_success(self, client):
        """Test successful password change"""
        change_data = {
            "current_password": "current_password",
            "new_password": "new_password123"
        }
        
        with patch('app.api.v1.auth.get_current_user') as mock_user:
            mock_user.return_value = {"uid": "user123", "email": "test@example.com"}
            
            with patch('app.api.v1.auth.auth_service.change_password') as mock_change:
                mock_change.return_value = {"message": "Password changed successfully"}
                
                response = client.post("/api/v1/auth/change-password", json=change_data)
                
                assert response.status_code == 200
                assert response.json()["message"] == "Password changed successfully"
    
    def test_rate_limit_exceeded(self, client):
        """Test rate limit error handling"""
        login_data = {
            "email": "test@example.com",
            "password": "password123"
        }
        
        with patch('app.api.v1.auth.auth_service.login_user') as mock_login:
            mock_login.side_effect = RateLimitError("Rate limit exceeded")
            
            response = client.post("/api/v1/auth/login", json=login_data)
            
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_resend_verification_success(self, client):
        """Test successful verification email resend"""
        resend_data = {"email": "test@example.com"}
        
        with patch('app.api.v1.auth.auth_service.resend_verification') as mock_resend:
            mock_resend.return_value = {"message": "Verification email sent"}
            
            response = client.post("/api/v1/auth/resend-verification", json=resend_data)
            
            assert response.status_code == 200
            assert response.json()["message"] == "Verification email sent" 