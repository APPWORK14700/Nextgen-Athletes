from typing import Optional, Dict, Any, List
import logging
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from firebase_admin import auth
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from ..firebaseConfig import get_auth_client, create_user as firebase_create_user
from ..models.user import UserCreate, UserLogin, AuthResponse
from .database_service import DatabaseService, DatabaseError
from ..utils.athlete_utils import AthleteUtils

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Custom exception for authentication errors"""
    pass


class UserRegistrationError(Exception):
    """Custom exception for user registration errors"""
    pass


class SessionExpiredError(Exception):
    """Custom exception for expired sessions"""
    pass


class AuthService:
    """Authentication service using Firebase Auth with proper session management"""
    
    def __init__(self):
        self.auth_client = get_auth_client()
        self.user_service = DatabaseService("users")
        self.user_profile_service = DatabaseService("user_profiles")
        self.session_service = DatabaseService("user_sessions")
        
        # Security configuration
        self.jwt_secret = self._get_jwt_secret()
        self.jwt_algorithm = "HS256"
        self.access_token_expiry = timedelta(hours=1)  # 1 hour
        self.refresh_token_expiry = timedelta(days=30)  # 30 days
        self.max_sessions_per_user = 5
        self.session_timeout = timedelta(hours=24)  # 24 hours
        
    def _get_jwt_secret(self) -> str:
        """Get JWT secret from environment or generate a secure one"""
        import os
        secret = os.getenv('JWT_SECRET')
        if not secret:
            # Generate a secure random secret if not provided
            secret = secrets.token_urlsafe(64)
            logger.warning("JWT_SECRET not found in environment. Generated temporary secret.")
        return secret
    
    def _generate_session_id(self) -> str:
        """Generate a secure session ID"""
        return secrets.token_urlsafe(32)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using secure hashing"""
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_obj.hex()}"
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            salt, hash_hex = hashed.split('$', 1)
            hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return hash_obj.hex() == hash_hex
        except Exception:
            return False
    
    def _generate_tokens(self, user_id: str, session_id: str) -> Dict[str, str]:
        """Generate access and refresh tokens"""
        now = datetime.now(timezone.utc)
        
        # Access token payload
        access_payload = {
            'user_id': user_id,
            'session_id': session_id,
            'type': 'access',
            'iat': now,
            'exp': now + self.access_token_expiry
        }
        
        # Refresh token payload
        refresh_payload = {
            'user_id': user_id,
            'session_id': session_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + self.refresh_token_expiry
        }
        
        access_token = jwt.encode(access_payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        refresh_token = jwt.encode(refresh_payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': int(self.access_token_expiry.total_seconds())
        }
    
    def _validate_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """Validate JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            if payload.get('type') != token_type:
                raise AuthError(f"Invalid token type. Expected {token_type}")
            
            return payload
            
        except ExpiredSignatureError:
            raise SessionExpiredError("Token has expired")
        except InvalidTokenError:
            raise AuthError("Invalid token")
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise AuthError("Token validation failed")
    
    async def _create_user_session(self, user_id: str, ip_address: str = None, user_agent: str = None) -> str:
        """Create a new user session"""
        session_id = self._generate_session_id()
        now = datetime.now(timezone.utc)
        
        session_data = {
            'session_id': session_id,
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'created_at': now.isoformat(),
            'last_activity': now.isoformat(),
            'is_active': True,
            'expires_at': (now + self.session_timeout).isoformat()
        }
        
        await self.session_service.create(session_data, session_id)
        
        return session_id
    

    
    async def _update_session_activity(self, session_id: str) -> None:
        """Update session last activity timestamp"""
        try:
            now = datetime.now(timezone.utc)
            await self.session_service.update(session_id, {
                'last_activity': now.isoformat()
            })
        except Exception as e:
            logger.error(f"Error updating session activity for {session_id}: {e}")
    
    async def _validate_session(self, session_id: str) -> bool:
        """Validate if session is still active and not expired"""
        try:
            session = await self.session_service.get_by_id(session_id)
            if not session or not session.get('is_active'):
                return False
            
            # Check if session has expired
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now(timezone.utc) > expires_at:
                await self.session_service.update(session_id, {'is_active': False})
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating session {session_id}: {e}")
            return False
    
    async def _generate_unique_username(self, first_name: str, last_name: str) -> str:
        """Generate a unique username for the user"""
        base_username = f"{first_name.lower()}{last_name.lower()}"
        username = base_username
        
        # Check if username exists and generate alternatives
        counter = 1
        while True:
            existing_user = await self.user_profile_service.get_by_field("username", username)
            if not existing_user:
                break
            username = f"{base_username}{counter}"
            counter += 1
            
            # Prevent infinite loop
            if counter > 100:
                # Fallback to timestamp-based username
                timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                username = f"{base_username}{timestamp}"
                break
        
        return username

    async def _update_last_login(self, user_id: str) -> None:
        """Update last login timestamp using transaction"""
        async def update_last_login_transaction(transaction):
            profile_ref = self.user_profile_service.collection.document(user_id)
            transaction.update(profile_ref, {
                "last_login": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
        
        await self.user_profile_service.run_transaction(update_last_login_transaction)

    async def register_user(self, user_data: UserCreate, ip_address: str = None, user_agent: str = None) -> AuthResponse:
        """Register a new user with transaction support for data consistency"""
        try:
            # Sanitize input data
            sanitized_data = AthleteUtils.validate_and_sanitize_input(
                user_data.dict(),
                required_fields=['email', 'password', 'first_name', 'last_name', 'role'],
                max_field_length=100
            )
            
            # Validate email format
            if not AthleteUtils.validate_email(sanitized_data['email']):
                raise UserRegistrationError("Invalid email format")
            
            # Validate password strength
            if len(sanitized_data['password']) < 8:
                raise UserRegistrationError("Password must be at least 8 characters long")
            
            # Create Firebase user first
            display_name = f"{sanitized_data['first_name']} {sanitized_data['last_name']}"
            firebase_user = firebase_create_user(
                email=sanitized_data['email'],
                password=sanitized_data['password'],
                display_name=display_name
            )
            
            # Generate unique username
            unique_username = await self._generate_unique_username(
                sanitized_data['first_name'], 
                sanitized_data['last_name']
            )
            
            # Use transaction to ensure both user and profile documents are created atomically
            async def create_user_transaction(transaction):
                # Create user document
                user_doc = {
                    "id": firebase_user["uid"],
                    "email": sanitized_data['email'],
                    "email_verified": firebase_user["email_verified"],
                    "role": sanitized_data['role'],
                    "status": "active",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Create user profile document
                profile_doc = {
                    "user_id": firebase_user["uid"],
                    "username": unique_username,
                    "first_name": sanitized_data['first_name'],
                    "last_name": sanitized_data['last_name'],
                    "profile_completion": 0,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Create documents in transaction
                user_ref = self.user_service.collection.document(firebase_user["uid"])
                profile_ref = self.user_profile_service.collection.document(firebase_user["uid"])
                
                transaction.set(user_ref, user_doc)
                transaction.set(profile_ref, profile_doc)
            
            await self.user_service.run_transaction(create_user_transaction)
            
            # Create session and generate tokens
            session_id = await self._create_user_session(
                firebase_user["uid"], 
                ip_address, 
                user_agent
            )
            tokens = self._generate_tokens(firebase_user["uid"], session_id)
            
            return AuthResponse(
                user_id=firebase_user["uid"],
                email=sanitized_data['email'],
                username=unique_username,
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token'],
                expires_in=tokens['expires_in']
            )
            
        except (UserRegistrationError, AuthError):
            raise
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            raise UserRegistrationError(f"Failed to register user: {str(e)}")

    async def login_user(self, user_data: UserLogin, ip_address: str = None, user_agent: str = None) -> AuthResponse:
        """Login user with session management"""
        try:
            # Sanitize input
            sanitized_data = AthleteUtils.validate_and_sanitize_input(
                user_data.dict(),
                required_fields=['email', 'password'],
                max_field_length=100
            )
            
            # Verify Firebase credentials
            try:
                firebase_user = self.auth_client.get_user_by_email(sanitized_data['email'])
            except Exception:
                raise AuthError("Invalid email or password")
            
            # Get user profile
            user_profile = await self.user_profile_service.get_by_field("user_id", firebase_user.uid)
            if not user_profile:
                raise AuthError("User profile not found")
            
            # Check if user is active
            if user_profile.get('status') != 'active':
                raise AuthError("User account is not active")
            
            # Create session and generate tokens
            session_id = await self._create_user_session(
                firebase_user.uid, 
                ip_address, 
                user_agent
            )
            tokens = self._generate_tokens(firebase_user.uid, session_id)
            
            # Update last login
            await self._update_last_login(firebase_user.uid)
            
            return AuthResponse(
                user_id=firebase_user.uid,
                email=firebase_user.email,
                username=user_profile.get('username'),
                access_token=tokens['access_token'],
                refresh_token=tokens['refresh_token'],
                expires_in=tokens['expires_in']
            )
            
        except (AuthError, SessionExpiredError):
            raise
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            raise AuthError(f"Login failed: {str(e)}")
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Refresh access token using refresh token"""
        try:
            # Validate refresh token
            payload = self._validate_token(refresh_token, 'refresh')
            user_id = payload['user_id']
            session_id = payload['session_id']
            
            # Validate session
            if not await self._validate_session(session_id):
                raise SessionExpiredError("Session has expired")
            
            # Generate new tokens
            tokens = self._generate_tokens(user_id, session_id)
            
            # Update session activity
            await self._update_session_activity(session_id)
            
            return {
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expires_in': tokens['expires_in']
            }
            
        except (AuthError, SessionExpiredError):
            raise
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise AuthError(f"Token refresh failed: {str(e)}")
    
    async def logout_user(self, access_token: str) -> bool:
        """Logout user by invalidating session"""
        try:
            # Validate access token
            payload = self._validate_token(access_token, 'access')
            session_id = payload['session_id']
            
            # Invalidate session
            await self.session_service.update(session_id, {'is_active': False})
            
            return True
            
        except (AuthError, SessionExpiredError):
            raise
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            raise AuthError(f"Logout failed: {str(e)}")
    
    async def validate_token(self, access_token: str) -> Dict[str, Any]:
        """Validate access token and return user info"""
        try:
            # Validate token
            payload = self._validate_token(access_token, 'access')
            user_id = payload['user_id']
            session_id = payload['session_id']
            
            # Validate session
            if not await self._validate_session(session_id):
                raise SessionExpiredError("Session has expired")
            
            # Update session activity
            await self._update_session_activity(session_id)
            
            # Get user info
            user = await self.user_service.get_by_id(user_id)
            user_profile = await self.user_profile_service.get_by_field("user_id", user_id)
            
            return {
                'user_id': user_id,
                'email': user.get('email') if user else None,
                'username': user_profile.get('username') if user_profile else None,
                'role': user.get('role') if user else None,
                'status': user.get('status') if user else None
            }
            
        except (AuthError, SessionExpiredError):
            raise
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            raise AuthError(f"Token validation failed: {str(e)}")
    
    async def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke all active sessions for a user (for security purposes)"""
        try:
            # Get all active sessions for user
            user_sessions = await self.session_service.query([
                ('user_id', '==', user_id),
                ('is_active', '==', True)
            ])
            
            # Deactivate all sessions
            for session in user_sessions:
                await self.session_service.update(session['id'], {'is_active': False})
            
            logger.info(f"Revoked {len(user_sessions)} sessions for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking sessions for user {user_id}: {e}")
            return False
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active sessions for a user"""
        try:
            sessions = await self.session_service.query([
                ('user_id', '==', user_id),
                ('is_active', '==', True)
            ])
            
            # Remove sensitive information
            for session in sessions:
                session.pop('session_id', None)
                session.pop('user_id', None)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions for user {user_id}: {e}")
            return [] 