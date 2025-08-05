from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from .base import BaseModelWithID


class User(BaseModelWithID):
    """User model for authentication and basic user info"""
    email: EmailStr
    email_verified: bool = False
    role: Literal["athlete", "scout", "admin"] = "athlete"
    status: Literal["active", "suspended", "deleted"] = "active"


class UserSettings(BaseModel):
    """User settings and preferences"""
    notifications_enabled: bool = True
    privacy_level: Literal["public", "private", "friends_only"] = "public"


class UserProfile(BaseModelWithID):
    """User profile with additional details"""
    user_id: str
    username: str
    phone_number: Optional[str] = None
    is_verified: bool = False
    is_active: bool = True
    last_login: Optional[datetime] = None
    profile_completion: int = Field(default=0, ge=0, le=100)
    settings: UserSettings = Field(default_factory=UserSettings)


class UserCreate(BaseModel):
    """Model for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Literal["athlete", "scout"] = "athlete"
    first_name: str
    last_name: str


class UserLogin(BaseModel):
    """Model for user login"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Model for updating user profile"""
    username: Optional[str] = None
    phone_number: Optional[str] = None
    settings: Optional[UserSettings] = None


class PasswordChange(BaseModel):
    """Model for password change"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class PasswordReset(BaseModel):
    """Model for password reset"""
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerification(BaseModel):
    """Model for email verification"""
    token: str


class AuthResponse(BaseModel):
    """Authentication response model"""
    access_token: str
    token_type: str = "bearer"
    user_id: Optional[str] = None
    email: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Model for token refresh"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Model for token refresh response"""
    access_token: str
    refresh_token: str 