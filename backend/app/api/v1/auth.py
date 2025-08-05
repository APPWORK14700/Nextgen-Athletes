from fastapi import APIRouter, Depends, HTTPException, status
from slowapi.util import get_remote_address
from slowapi import Limiter
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer
from ...services.auth_service import AuthService
from ...models.user import (
    UserCreate, UserLogin, AuthResponse, RefreshTokenRequest, 
    RefreshTokenResponse, PasswordChange, PasswordReset, EmailVerification
)
from ...models.base import SuccessResponse
from ...api.exceptions import ValidationException, AuthenticationException
from ...models.user import User
from ...api.dependencies import get_current_user

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("10/minute")
async def register(
    user_data: UserCreate,
    request: Request
):
    """Register a new user"""
    try:
        auth_service = AuthService()
        response = await auth_service.register_user(user_data)
        return response
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("20/minute")
async def login(
    login_data: UserLogin,
    request: Request
):
    """Login user"""
    try:
        auth_service = AuthService()
        response = await auth_service.login_user(login_data)
        return response
    except ValueError as e:
        raise AuthenticationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(verification_data: EmailVerification):
    """Verify user email"""
    try:
        auth_service = AuthService()
        await auth_service.verify_email(verification_data.token)
        return SuccessResponse(message="Email verified successfully")
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )


@router.post("/resend-verification", response_model=SuccessResponse)
@limiter.limit("5/minute")
async def resend_verification(
    email_data: dict,
    request: Request
):
    """Resend email verification"""
    try:
        # In production, implement email resend logic
        return SuccessResponse(message="Verification email sent")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification email"
        )


@router.post("/forgot-password", response_model=SuccessResponse)
@limiter.limit("5/minute")
async def forgot_password(
    email_data: dict,
    request: Request
):
    """Send password reset email"""
    try:
        auth_service = AuthService()
        await auth_service.reset_password(email_data["email"])
        return SuccessResponse(message="Password reset email sent")
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send password reset email"
        )


@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(reset_data: PasswordReset):
    """Reset password using token"""
    try:
        # In production, implement password reset logic
        return SuccessResponse(message="Password reset successfully")
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user)
):
    """Change password for authenticated user"""
    try:
        auth_service = AuthService()
        await auth_service.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password
        )
        return SuccessResponse(message="Password changed successfully")
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(refresh_data: RefreshTokenRequest):
    """Refresh access token"""
    try:
        auth_service = AuthService()
        response = await auth_service.refresh_token(refresh_data.refresh_token)
        return response
    except ValueError as e:
        raise AuthenticationException(str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user"""
    try:
        auth_service = AuthService()
        await auth_service.logout(current_user.id)
        return SuccessResponse(message="Logged out successfully")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        ) 