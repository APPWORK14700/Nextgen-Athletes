import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from app.services.auth_service import AuthService
from app.api.exceptions import (
    ValidationError, AuthenticationError, AuthorizationError,
    ResourceNotFoundError, RateLimitError
)


class TestAuthService:
    """Test cases for AuthService"""
    
    @pytest.mark.asyncio
    async def test_register_user(self, mock_auth):
        """Test user registration"""
        service = AuthService()
        service.auth = mock_auth
        
        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "role": "athlete"
        }
        
        # Mock successful user creation
        mock_user = AsyncMock()
        mock_user.uid = "user123"
        mock_user.email = "test@example.com"
        mock_auth.create_user.return_value = mock_user
        
        result = await service.register_user(user_data)
        
        assert result is not None
        assert result["uid"] == "user123"
        assert result["email"] == "test@example.com"
        mock_auth.create_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, mock_auth):
        """Test user registration with duplicate email"""
        service = AuthService()
        service.auth = mock_auth
        
        user_data = {
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "athlete"
        }
        
        # Mock email already exists error
        mock_auth.create_user.side_effect = Exception("Email already exists")
        
        with pytest.raises(ValidationError):
            await service.register_user(user_data)
    
    @pytest.mark.asyncio
    async def test_login_user(self, mock_auth):
        """Test user login"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful login
        mock_auth.verify_id_token.return_value = {
            "uid": "test_user_id",
            "email": "test@example.com"
        }
        
        result = await service.login_user("test@example.com", "password123")
        
        assert result["uid"] == "test_user_id"
        assert result["email"] == "test@example.com"
        assert "access_token" in result
        assert "refresh_token" in result
    
    @pytest.mark.asyncio
    async def test_login_user_invalid_credentials(self, mock_auth):
        """Test login with invalid credentials"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock authentication failure
        mock_auth.verify_id_token.side_effect = Exception("Invalid credentials")
        
        with pytest.raises(AuthenticationError):
            await service.login_user("test@example.com", "wrong_password")
    
    @pytest.mark.asyncio
    async def test_verify_token(self, mock_auth):
        """Test token verification"""
        service = AuthService()
        service.auth = mock_auth
        
        mock_auth.verify_id_token.return_value = {
            "uid": "test_user_id",
            "email": "test@example.com",
            "role": "athlete"
        }
        
        result = await service.verify_token("valid_token")
        
        assert result["uid"] == "test_user_id"
        assert result["email"] == "test@example.com"
        assert result["role"] == "athlete"
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, mock_auth):
        """Test invalid token verification"""
        service = AuthService()
        service.auth = mock_auth
        
        mock_auth.verify_id_token.side_effect = Exception("Invalid token")
        
        with pytest.raises(AuthenticationError):
            await service.verify_token("invalid_token")
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, mock_auth):
        """Test token refresh"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful token refresh
        mock_auth.verify_id_token.return_value = {
            "uid": "test_user_id",
            "email": "test@example.com"
        }
        
        result = await service.refresh_token("valid_refresh_token")
        
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["access_token"] != "valid_refresh_token"
    
    @pytest.mark.asyncio
    async def test_change_password(self, mock_auth):
        """Test password change"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful password change
        mock_auth.update_user.return_value = AsyncMock()
        
        result = await service.change_password("user123", "new_password")
        
        assert result["message"] == "Password changed successfully"
        mock_auth.update_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_verification_email(self, mock_auth):
        """Test sending verification email"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock email verification
        mock_auth.generate_email_verification_link.return_value = "https://verification-link.com"
        
        result = await service.send_verification_email("test@example.com")
        
        assert result["message"] == "Verification email sent"
        mock_auth.generate_email_verification_link.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_email(self, mock_auth):
        """Test email verification"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful email verification
        mock_auth.verify_id_token.return_value = {
            "uid": "user123",
            "email_verified": True
        }
        
        result = await service.verify_email("verification_token")
        
        assert result["message"] == "Email verified successfully"
    
    @pytest.mark.asyncio
    async def test_forgot_password(self, mock_auth):
        """Test forgot password"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock password reset email
        mock_auth.generate_password_reset_link.return_value = "https://reset-link.com"
        
        result = await service.forgot_password("test@example.com")
        
        assert result["message"] == "Password reset email sent"
        mock_auth.generate_password_reset_link.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reset_password(self, mock_auth):
        """Test password reset"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful password reset
        mock_auth.verify_password_reset_code.return_value = "user123"
        mock_auth.update_user.return_value = AsyncMock()
        
        result = await service.reset_password("reset_token", "new_password")
        
        assert result["message"] == "Password reset successfully"
        mock_auth.update_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_logout_user(self, mock_auth):
        """Test user logout"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful logout (token invalidation)
        mock_auth.revoke_refresh_tokens.return_value = AsyncMock()
        
        result = await service.logout("user123")
        
        assert result["message"] == "Logged out successfully"
        mock_auth.revoke_refresh_tokens.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_user(self, mock_auth):
        """Test user deletion"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful user deletion
        mock_auth.delete_user.return_value = AsyncMock()
        
        result = await service.delete_user("user123")
        
        assert result["message"] == "User deleted successfully"
        mock_auth.delete_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_role(self, mock_auth):
        """Test updating user role"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock successful role update
        mock_auth.set_custom_user_claims.return_value = AsyncMock()
        
        result = await service.update_user_role("user123", "scout")
        
        assert result["message"] == "User role updated successfully"
        assert result["role"] == "scout"
        mock_auth.set_custom_user_claims.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_by_email(self, mock_auth):
        """Test getting user by email"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock user retrieval
        mock_user = AsyncMock()
        mock_user.uid = "user123"
        mock_user.email = "test@example.com"
        mock_user.email_verified = True
        mock_auth.get_user_by_email.return_value = mock_user
        
        result = await service.get_user_by_email("test@example.com")
        
        assert result["uid"] == "user123"
        assert result["email"] == "test@example.com"
        assert result["email_verified"] is True
    
    @pytest.mark.asyncio
    async def test_validate_token_expiry(self, mock_auth):
        """Test token expiry validation"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock expired token
        expired_time = datetime.now() - timedelta(hours=2)
        mock_auth.verify_id_token.return_value = {
            "uid": "user123",
            "exp": int(expired_time.timestamp())
        }
        
        with pytest.raises(AuthenticationError, match="Token expired"):
            await service.verify_token("expired_token")
    
    @pytest.mark.asyncio
    async def test_rate_limit_auth_attempts(self, mock_auth):
        """Test rate limiting on authentication attempts"""
        service = AuthService()
        service.auth = mock_auth
        
        # Mock multiple failed attempts
        mock_auth.verify_id_token.side_effect = Exception("Invalid credentials")
        
        # Simulate multiple failed login attempts
        for _ in range(5):
            with pytest.raises(AuthenticationError):
                await service.login_user("test@example.com", "wrong_password")
        
        # Next attempt should be rate limited
        with pytest.raises(RateLimitError):
            await service.login_user("test@example.com", "wrong_password") 