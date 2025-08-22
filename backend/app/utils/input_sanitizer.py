"""
Input sanitization utilities for preventing injection attacks and ensuring data safety
"""
import re
import html
from typing import Optional, Union, List
from urllib.parse import quote, unquote

class InputSanitizer:
    """Utility class for sanitizing user inputs"""
    
    # Username validation patterns
    USERNAME_MIN_LENGTH = 3
    USERNAME_MAX_LENGTH = 30
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    # Email validation pattern
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    # Phone number validation pattern
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    
    @classmethod
    def sanitize_username(cls, username: str) -> str:
        """
        Sanitize username input to prevent injection attacks
        
        Args:
            username: Raw username input
            
        Returns:
            Sanitized username
            
        Raises:
            ValueError: If username is invalid
        """
        if not username:
            raise ValueError("Username cannot be empty")
        
        # Remove leading/trailing whitespace
        username = username.strip()
        
        # Check length
        if len(username) < cls.USERNAME_MIN_LENGTH:
            raise ValueError(f"Username must be at least {cls.USERNAME_MIN_LENGTH} characters long")
        
        if len(username) > cls.USERNAME_MAX_LENGTH:
            raise ValueError(f"Username cannot exceed {cls.USERNAME_MAX_LENGTH} characters")
        
        # Check pattern
        if not cls.USERNAME_PATTERN.match(username):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        
        # Convert to lowercase for consistency
        return username.lower()
    
    @classmethod
    def sanitize_email(cls, email: str) -> str:
        """
        Sanitize email input
        
        Args:
            email: Raw email input
            
        Returns:
            Sanitized email
            
        Raises:
            ValueError: If email is invalid
        """
        if not email:
            raise ValueError("Email cannot be empty")
        
        # Remove leading/trailing whitespace and convert to lowercase
        email = email.strip().lower()
        
        # Check pattern
        if not cls.EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email format")
        
        return email
    
    @classmethod
    def sanitize_phone_number(cls, phone: str) -> Optional[str]:
        """
        Sanitize phone number input
        
        Args:
            phone: Raw phone number input
            
        Returns:
            Sanitized phone number or None if empty
        """
        if not phone:
            return None
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone.strip())
        
        # Ensure it starts with + for international format
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        # Validate pattern
        if not cls.PHONE_PATTERN.match(cleaned):
            raise ValueError("Invalid phone number format")
        
        return cleaned
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = 1000) -> str:
        """
        Sanitize general text input
        
        Args:
            text: Raw text input
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Check length
        if len(text) > max_length:
            text = text[:max_length]
        
        # HTML escape to prevent XSS
        text = html.escape(text)
        
        return text
    
    @classmethod
    def sanitize_url(cls, url: str) -> Optional[str]:
        """
        Sanitize URL input
        
        Args:
            url: Raw URL input
            
        Returns:
            Sanitized URL or None if empty
        """
        if not url:
            return None
        
        url = url.strip()
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Basic URL validation
        try:
            # Simple regex for basic URL validation
            url_pattern = re.compile(
                r'^https?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
                r'localhost|'  # localhost...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(url):
                raise ValueError("Invalid URL format")
            
            return url
            
        except Exception:
            raise ValueError("Invalid URL format")
    
    @classmethod
    def sanitize_search_query(cls, query: str, max_length: int = 100) -> str:
        """
        Sanitize search query input
        
        Args:
            query: Raw search query
            max_length: Maximum allowed length
            
        Returns:
            Sanitized search query
        """
        if not query:
            return ""
        
        # Remove leading/trailing whitespace
        query = query.strip()
        
        # Check length
        if len(query) > max_length:
            query = query[:max_length]
        
        # Remove potentially dangerous characters but keep search functionality
        # Allow letters, numbers, spaces, and common punctuation
        query = re.sub(r'[<>"\']', '', query)
        
        return query
    
    @classmethod
    def sanitize_list(cls, items: List[str], max_items: int = 100) -> List[str]:
        """
        Sanitize a list of strings
        
        Args:
            items: List of raw strings
            max_items: Maximum number of items allowed
            
        Returns:
            List of sanitized strings
        """
        if not items:
            return []
        
        # Limit number of items
        if len(items) > max_items:
            items = items[:max_items]
        
        # Sanitize each item
        sanitized = []
        for item in items:
            if item and isinstance(item, str):
                sanitized.append(cls.sanitize_text(item, max_length=100))
        
        return sanitized
    
    @classmethod
    def validate_role(cls, role: str) -> str:
        """
        Validate and sanitize user role
        
        Args:
            role: Raw role input
            
        Returns:
            Validated role
            
        Raises:
            ValueError: If role is invalid
        """
        valid_roles = ["athlete", "scout", "admin"]
        
        if not role:
            raise ValueError("Role cannot be empty")
        
        role = role.strip().lower()
        
        if role not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
        
        return role
    
    @classmethod
    def validate_status(cls, status: str) -> str:
        """
        Validate and sanitize user status
        
        Args:
            status: Raw status input
            
        Returns:
            Validated status
            
        Raises:
            ValueError: If status is invalid
        """
        valid_statuses = ["active", "suspended", "deleted"]
        
        if not status:
            raise ValueError("Status cannot be empty")
        
        status = status.strip().lower()
        
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        return status

# Convenience functions for common sanitization tasks
def sanitize_username(username: str) -> str:
    """Convenience function for username sanitization"""
    return InputSanitizer.sanitize_username(username)

def sanitize_email(email: str) -> str:
    """Convenience function for email sanitization"""
    return InputSanitizer.sanitize_email(email)

def sanitize_phone_number(phone: str) -> Optional[str]:
    """Convenience function for phone number sanitization"""
    return InputSanitizer.sanitize_phone_number(phone)

def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Convenience function for text sanitization"""
    return InputSanitizer.sanitize_text(text, max_length)

def sanitize_search_query(query: str, max_length: int = 100) -> str:
    """Convenience function for search query sanitization"""
    return InputSanitizer.sanitize_search_query(query, max_length) 