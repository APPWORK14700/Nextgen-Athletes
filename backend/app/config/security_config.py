"""
Security Configuration for Athletes Networking App

This module provides centralized security configuration and utilities
for the entire application.
"""

import os
from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class SecurityLevel(Enum):
    """Security levels for different environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms"""
    AES_256 = "aes-256-gcm"
    CHACHA20 = "chacha20-poly1305"


@dataclass
class SecurityConfig:
    """Comprehensive security configuration"""
    
    # Environment
    environment: SecurityLevel = SecurityLevel.DEVELOPMENT
    
    # Authentication & Authorization
    jwt_secret: str = None
    jwt_algorithm: str = "HS256"
    access_token_expiry_hours: int = 1
    refresh_token_expiry_days: int = 30
    max_sessions_per_user: int = 5
    session_timeout_hours: int = 24
    password_min_length: int = 8
    password_require_special_chars: bool = True
    password_require_numbers: bool = True
    password_require_uppercase: bool = True
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    
    # Input Validation & Sanitization
    max_input_length: int = 1000
    max_filename_length: int = 255
    max_file_size_mb: int = 100
    allowed_file_types: List[str] = None
    blocked_file_extensions: List[str] = None
    enable_html_sanitization: bool = True
    allowed_html_tags: List[str] = None
    enable_xss_protection: bool = True
    enable_sql_injection_protection: bool = True
    
    # Rate Limiting
    enable_rate_limiting: bool = True
    rate_limit_window_seconds: int = 3600
    max_requests_per_window: int = 100
    max_uploads_per_hour: int = 50
    max_searches_per_minute: int = 30
    
    # File Security
    enable_malware_scanning: bool = True
    virus_total_api_key: str = None
    max_scan_file_size_mb: int = 50
    enable_file_hash_verification: bool = True
    blocked_file_patterns: List[str] = None
    
    # Data Encryption
    enable_encryption_at_rest: bool = False
    encryption_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256
    encryption_key: str = None
    enable_field_level_encryption: bool = False
    sensitive_fields: List[str] = None
    
    # Audit & Logging
    enable_audit_logging: bool = True
    audit_retention_days: int = 90
    log_sensitive_operations: bool = True
    enable_security_events: bool = True
    
    # Network Security
    enable_cors: bool = True
    allowed_origins: List[str] = None
    enable_https_only: bool = True
    enable_hsts: bool = True
    enable_csp: bool = True
    
    # API Security
    enable_api_key_validation: bool = False
    api_key_header: str = "X-API-Key"
    enable_request_signing: bool = False
    max_request_size_mb: int = 10
    
    def __post_init__(self):
        """Set default values after initialization"""
        if self.allowed_file_types is None:
            self.allowed_file_types = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'video/mp4', 'video/avi', 'video/mov', 'video/wmv',
                'application/pdf', 'application/msword',
                'audio/mpeg', 'audio/wav', 'audio/ogg'
            ]
        
        if self.blocked_file_extensions is None:
            self.blocked_file_extensions = [
                '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
                '.vbs', '.js', '.jar', '.msi', '.dll', '.sys'
            ]
        
        if self.allowed_html_tags is None:
            self.allowed_html_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
        
        if self.blocked_file_patterns is None:
            self.blocked_file_patterns = [
                r'\.\.', r'\.\.\.', r'\.\.\.\.',  # Directory traversal
                r'<script', r'</script>',  # Script tags
                r'javascript:', r'vbscript:',  # Script protocols
                r'data:', r'file:', r'ftp:'  # Dangerous protocols
            ]
        
        if self.sensitive_fields is None:
            self.sensitive_fields = [
                'password', 'token', 'secret', 'key', 'credential',
                'api_key', 'private_key', 'connection_string'
            ]
        
        if self.allowed_origins is None:
            self.allowed_origins = ['http://localhost:3000', 'https://localhost:3000']
        
        # Set JWT secret from environment if not provided
        if not self.jwt_secret:
            self.jwt_secret = os.getenv('JWT_SECRET')
        
        # Set encryption key from environment if not provided
        if not self.encryption_key:
            self.encryption_key = os.getenv('ENCRYPTION_KEY')
        
        # Set VirusTotal API key from environment if not provided
        if not self.virus_total_api_key:
            self.virus_total_api_key = os.getenv('VIRUS_TOTAL_API_KEY')
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == SecurityLevel.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == SecurityLevel.DEVELOPMENT
    
    def get_file_size_limit_bytes(self) -> int:
        """Get file size limit in bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    def get_scan_file_size_limit_bytes(self) -> int:
        """Get malware scan file size limit in bytes"""
        return self.max_scan_file_size_mb * 1024 * 1024
    
    def get_request_size_limit_bytes(self) -> int:
        """Get request size limit in bytes"""
        return self.max_request_size_mb * 1024 * 1024
    
    def should_enable_strict_security(self) -> bool:
        """Check if strict security measures should be enabled"""
        return self.is_production() or self.environment == SecurityLevel.STAGING
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration"""
        if not self.enable_cors:
            return {}
        
        return {
            'allow_origins': self.allowed_origins,
            'allow_credentials': True,
            'allow_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            'allow_headers': ['*'],
            'max_age': 3600
        }
    
    def get_security_headers(self) -> Dict[str, str]:
        """Get security headers configuration"""
        headers = {}
        
        if self.enable_https_only:
            headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        if self.enable_csp:
            headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        
        if self.enable_hsts:
            headers['X-Content-Type-Options'] = 'nosniff'
            headers['X-Frame-Options'] = 'DENY'
            headers['X-XSS-Protection'] = '1; mode=block'
        
        return headers


def get_security_config(environment: str = None) -> SecurityConfig:
    """Get security configuration for the specified environment
    
    Args:
        environment: Environment name (development, staging, production)
        
    Returns:
        SecurityConfig instance
    """
    if environment is None:
        environment = os.getenv('ENVIRONMENT', 'development').lower()
    
    # Map environment string to SecurityLevel enum
    env_mapping = {
        'development': SecurityLevel.DEVELOPMENT,
        'staging': SecurityLevel.STAGING,
        'production': SecurityLevel.PRODUCTION
    }
    
    security_level = env_mapping.get(environment, SecurityLevel.DEVELOPMENT)
    
    # Create configuration with environment-specific overrides
    config = SecurityConfig(environment=security_level)
    
    # Apply environment-specific overrides
    if security_level == SecurityLevel.PRODUCTION:
        config.enable_encryption_at_rest = True
        config.enable_field_level_encryption = True
        config.enable_malware_scanning = True
        config.enable_audit_logging = True
        config.enable_security_events = True
        config.enable_https_only = True
        config.enable_hsts = True
        config.enable_csp = True
        config.max_sessions_per_user = 3  # Stricter in production
        config.session_timeout_hours = 12  # Shorter sessions in production
    
    elif security_level == SecurityLevel.STAGING:
        config.enable_encryption_at_rest = True
        config.enable_malware_scanning = True
        config.enable_audit_logging = True
        config.enable_https_only = True
    
    # Development environment uses default values (less strict)
    
    return config


def validate_security_config(config: SecurityConfig) -> List[str]:
    """Validate security configuration and return any issues
    
    Args:
        config: SecurityConfig instance to validate
        
    Returns:
        List of validation issues (empty if valid)
    """
    issues = []
    
    # Check required fields for production
    if config.is_production():
        if not config.jwt_secret:
            issues.append("JWT_SECRET is required in production")
        
        if not config.encryption_key:
            issues.append("ENCRYPTION_KEY is required in production")
        
        if config.enable_malware_scanning and not config.virus_total_api_key:
            issues.append("VIRUS_TOTAL_API_KEY is required when malware scanning is enabled")
    
    # Check configuration consistency
    if config.access_token_expiry_hours >= config.refresh_token_expiry_days * 24:
        issues.append("Access token expiry should be less than refresh token expiry")
    
    if config.max_file_size_mb > 1000:
        issues.append("Maximum file size should not exceed 1000MB")
    
    if config.max_requests_per_window > 10000:
        issues.append("Rate limit too high, consider reducing max_requests_per_window")
    
    return issues


# Global security configuration instance
_security_config = None


def get_global_security_config() -> SecurityConfig:
    """Get global security configuration instance (singleton)"""
    global _security_config
    
    if _security_config is None:
        _security_config = get_security_config()
    
    return _security_config


def update_global_security_config(config: SecurityConfig) -> None:
    """Update global security configuration
    
    Args:
        config: New security configuration
    """
    global _security_config
    _security_config = config 