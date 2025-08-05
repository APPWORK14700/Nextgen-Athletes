from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta
import jwt
from firebase_admin import auth
from firebase_admin.auth import UserRecord

from ..firebaseConfig import get_auth_client, verify_firebase_token, create_user as firebase_create_user
from ..models.user import User, UserCreate, UserLogin, AuthResponse, RefreshTokenResponse
from .database_service import DatabaseService

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service using Firebase Auth"""
    
    def __init__(self):
        self.auth_client = get_auth_client()
        self.user_service = DatabaseService("users")
        self.user_profile_service = DatabaseService("user_profiles")
        self.secret_key = "your-secret-key"  # In production, use environment variable
        
    async def register_user(self, user_data: UserCreate) -> AuthResponse:
        """Register a new user"""
        try:
            # Create Firebase user
            display_name = f"{user_data.first_name} {user_data.last_name}"
            firebase_user = firebase_create_user(
                email=user_data.email,
                password=user_data.password,
                display_name=display_name
            )
            
            # Create user document in Firestore
            user_doc = {
                "id": firebase_user["uid"],
                "email": user_data.email,
                "email_verified": firebase_user["email_verified"],
                "role": user_data.role,
                "status": "active"
            }
            
            await self.user_service.create(user_doc, firebase_user["uid"])
            
            # Create user profile
            profile_doc = {
                "user_id": firebase_user["uid"],
                "username": f"{user_data.first_name.lower()}{user_data.last_name.lower()}",
                "is_verified": False,
                "is_active": True,
                "profile_completion": 0,
                "settings": {
                    "notifications_enabled": True,
                    "privacy_level": "public"
                }
            }
            
            await self.user_profile_service.create(profile_doc)
            
            # Generate custom token
            custom_token = self.auth_client.create_custom_token(
                firebase_user["uid"],
                {"role": user_data.role}
            )
            
            return AuthResponse(
                access_token=custom_token.decode(),
                token_type="bearer",
                user_id=firebase_user["uid"],
                email=user_data.email
            )
            
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            raise
    
    async def login_user(self, login_data: UserLogin) -> AuthResponse:
        """Login user with email and password"""
        try:
            # Firebase handles email/password authentication
            # In a real implementation, you would verify the password here
            # For now, we'll assume the client has already authenticated with Firebase
            
            # Get user by email
            user_doc = await self.user_service.get_by_field("email", login_data.email)
            if not user_doc:
                raise ValueError("User not found")
            
            if user_doc["status"] != "active":
                raise ValueError("User account is not active")
            
            # Generate custom token
            custom_token = self.auth_client.create_custom_token(
                user_doc["id"],
                {"role": user_doc["role"]}
            )
            
            # Update last login
            await self.user_profile_service.update(
                user_doc["id"], 
                {"last_login": datetime.utcnow()}
            )
            
            return AuthResponse(
                access_token=custom_token.decode(),
                token_type="bearer",
                user_id=user_doc["id"],
                email=user_doc["email"]
            )
            
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            raise
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify Firebase ID token"""
        try:
            decoded_token = verify_firebase_token(token)
            return decoded_token
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            raise
    
    async def get_current_user(self, token: str) -> Optional[Dict[str, Any]]:
        """Get current user from token"""
        try:
            decoded_token = await self.verify_token(token)
            user_id = decoded_token.get("uid")
            
            if not user_id:
                return None
            
            user_doc = await self.user_service.get_by_id(user_id)
            if not user_doc or user_doc["status"] != "active":
                return None
            
            return user_doc
            
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None
    
    async def refresh_token(self, refresh_token: str) -> RefreshTokenResponse:
        """Refresh access token"""
        try:
            # Verify the refresh token
            decoded_token = await self.verify_token(refresh_token)
            user_id = decoded_token.get("uid")
            
            if not user_id:
                raise ValueError("Invalid refresh token")
            
            # Generate new access token
            custom_token = self.auth_client.create_custom_token(
                user_id,
                {"role": decoded_token.get("role", "athlete")}
            )
            
            # Generate new refresh token
            new_refresh_token = self.auth_client.create_custom_token(
                user_id,
                {"type": "refresh", "role": decoded_token.get("role", "athlete")}
            )
            
            return RefreshTokenResponse(
                access_token=custom_token.decode(),
                refresh_token=new_refresh_token.decode()
            )
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """Change user password"""
        try:
            # In a real implementation, you would verify the current password
            # For now, we'll assume the client has already verified it
            
            # Update password in Firebase
            self.auth_client.update_user(
                user_id,
                password=new_password
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            raise
    
    async def reset_password(self, email: str) -> bool:
        """Send password reset email"""
        try:
            # Firebase handles password reset emails
            # In a real implementation, you would send a custom email
            # For now, we'll just verify the user exists
            
            user_doc = await self.user_service.get_by_field("email", email)
            if not user_doc:
                raise ValueError("User not found")
            
            # In production, send password reset email here
            logger.info(f"Password reset requested for user: {email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            raise
    
    async def verify_email(self, token: str) -> bool:
        """Verify user email"""
        try:
            # In a real implementation, you would verify the email verification token
            # For now, we'll assume the token is valid
            
            # Update user email verification status
            # This would typically be done by updating the user document
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            raise
    
    async def logout(self, user_id: str) -> bool:
        """Logout user (invalidate tokens)"""
        try:
            # In Firebase, tokens are stateless and can't be invalidated server-side
            # The client should delete the token locally
            # You could maintain a blacklist of tokens if needed
            
            logger.info(f"User logged out: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            raise
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user account"""
        try:
            # Delete from Firebase Auth
            self.auth_client.delete_user(user_id)
            
            # Delete from Firestore (soft delete)
            await self.user_service.update(user_id, {"status": "deleted"})
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            raise
    
    def create_custom_token(self, user_id: str, claims: Dict[str, Any] = None) -> str:
        """Create custom token for user"""
        try:
            if claims is None:
                claims = {}
            
            custom_token = self.auth_client.create_custom_token(user_id, claims)
            return custom_token.decode()
            
        except Exception as e:
            logger.error(f"Error creating custom token: {e}")
            raise 