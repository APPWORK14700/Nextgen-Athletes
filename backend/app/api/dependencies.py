from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

from ..services.auth_service import AuthService
from ..models.user import User

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    try:
        auth_service = AuthService()
        token = credentials.credentials
        
        user_data = await auth_service.get_current_user(token)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return User(**user_data)
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    try:
        if not credentials:
            return None
        
        auth_service = AuthService()
        token = credentials.credentials
        
        user_data = await auth_service.get_current_user(token)
        if not user_data:
            return None
        
        return User(**user_data)
        
    except Exception as e:
        logger.error(f"Error getting current user (optional): {e}")
        return None


def require_role(required_role: str):
    """Dependency to require specific user role"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}"
            )
        return current_user
    
    return role_checker


def require_athlete():
    """Dependency to require athlete role"""
    return require_role("athlete")


def require_scout():
    """Dependency to require scout role"""
    return require_role("scout")


def require_admin():
    """Dependency to require admin role"""
    return require_role("admin")


def require_athlete_or_scout():
    """Dependency to require athlete or scout role"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in ["athlete", "scout"] and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Required role: athlete or scout"
            )
        return current_user
    
    return role_checker 