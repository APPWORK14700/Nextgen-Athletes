import os
import firebase_admin
from firebase_admin import credentials, firestore, auth
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global variables to store Firebase clients
_firestore_client: Optional[firestore.Client] = None
_auth_client: Optional[auth.Client] = None


def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global _firestore_client, _auth_client
    
    try:
        # Check if Firebase is already initialized
        if firebase_admin._apps:
            logger.info("Firebase already initialized")
            return
        
        # Get Firebase credentials
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and os.path.exists(cred_path):
            # Use service account key file
            cred = credentials.Certificate(cred_path)
        else:
            # Use default credentials (for production with service account)
            cred = credentials.ApplicationDefault()
        
        # Initialize Firebase app
        firebase_admin.initialize_app(cred)
        
        # Initialize clients
        _firestore_client = firestore.client()
        _auth_client = auth.Client()
        
        logger.info("Firebase initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise


def get_firestore_client() -> firestore.Client:
    """Get Firestore client instance"""
    global _firestore_client
    
    if _firestore_client is None:
        initialize_firebase()
    
    return _firestore_client


def get_auth_client() -> auth.Client:
    """Get Firebase Auth client instance"""
    global _auth_client
    
    if _auth_client is None:
        initialize_firebase()
    
    return _auth_client


def verify_firebase_token(token: str) -> dict:
    """Verify Firebase ID token and return user info"""
    try:
        auth_client = get_auth_client()
        decoded_token = auth_client.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise


def get_user_by_uid(uid: str) -> Optional[dict]:
    """Get user by Firebase UID"""
    try:
        auth_client = get_auth_client()
        user_record = auth_client.get_user(uid)
        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "email_verified": user_record.email_verified,
            "display_name": user_record.display_name,
            "photo_url": user_record.photo_url,
            "disabled": user_record.disabled,
            "custom_claims": user_record.custom_claims
        }
    except Exception as e:
        logger.error(f"Failed to get user by UID {uid}: {e}")
        return None


def create_user(email: str, password: str, display_name: str = None) -> dict:
    """Create a new Firebase user"""
    try:
        auth_client = get_auth_client()
        user_properties = {
            "email": email,
            "password": password,
        }
        
        if display_name:
            user_properties["display_name"] = display_name
        
        user_record = auth_client.create_user(**user_properties)
        
        return {
            "uid": user_record.uid,
            "email": user_record.email,
            "email_verified": user_record.email_verified,
            "display_name": user_record.display_name
        }
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise


def update_user_claims(uid: str, claims: dict):
    """Update user custom claims"""
    try:
        auth_client = get_auth_client()
        auth_client.set_custom_user_claims(uid, claims)
        logger.info(f"Updated claims for user {uid}")
    except Exception as e:
        logger.error(f"Failed to update user claims: {e}")
        raise


def delete_user(uid: str):
    """Delete a Firebase user"""
    try:
        auth_client = get_auth_client()
        auth_client.delete_user(uid)
        logger.info(f"Deleted user {uid}")
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise 