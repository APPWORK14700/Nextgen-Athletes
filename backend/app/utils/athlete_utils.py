"""
Athlete Utilities - Common functions and utilities used across athlete services
"""
from typing import Dict, Any, List
from datetime import datetime, date
from functools import lru_cache
import re
import html
import bleach
from urllib.parse import urlparse, urljoin


class AthleteUtils:
    """Utility class for common athlete operations"""
    
    # Allowed HTML tags and attributes for sanitization
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li']
    ALLOWED_ATTRIBUTES = {}
    ALLOWED_PROTOCOLS = ['http', 'https']
    
    @staticmethod
    def calculate_age(date_of_birth: str) -> int:
        """Calculate age from date of birth string"""
        try:
            birth_date = datetime.fromisoformat(date_of_birth).date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            return age
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def calculate_completion_percentage(profile_doc: Dict[str, Any], field_weights: Dict[str, int]) -> int:
        """Calculate profile completion percentage"""
        total_weight = sum(field_weights.values())
        filled_weight = sum(
            field_weights[field] for field, value in profile_doc.items() 
            if field in field_weights and value is not None and value != ""
        )
        
        return int((filled_weight / total_weight) * 100) if total_weight > 0 else 0
    
    @staticmethod
    def calculate_category_completion(profile_doc: Dict[str, Any], field_categories: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
        """Calculate completion by category"""
        category_completion = {}
        for category, fields in field_categories.items():
            filled_fields = sum(1 for field in fields if profile_doc.get(field) and profile_doc[field] != "")
            category_completion[category] = {
                "completed": filled_fields,
                "total": len(fields),
                "percentage": int((filled_fields / len(fields)) * 100) if fields else 0
            }
        
        return category_completion
    
    @staticmethod
    def get_missing_fields(profile_doc: Dict[str, Any], field_weights: Dict[str, int]) -> List[str]:
        """Get list of missing fields"""
        return [
            field for field, value in profile_doc.items() 
            if field in field_weights and (value is None or value == "")
        ]
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """Comprehensive string sanitization for security
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow safe HTML tags
            
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value) if value is not None else ""
        
        # Remove null bytes and control characters
        sanitized = value.replace('\x00', '').replace('\r', '').replace('\n', ' ')
        
        # HTML escape by default
        if not allow_html:
            sanitized = html.escape(sanitized)
        else:
            # Use bleach for HTML sanitization
            try:
                sanitized = bleach.clean(
                    sanitized,
                    tags=AthleteUtils.ALLOWED_TAGS,
                    attributes=AthleteUtils.ALLOWED_ATTRIBUTES,
                    protocols=AthleteUtils.ALLOWED_PROTOCOLS,
                    strip=True
                )
            except Exception:
                # Fallback to HTML escaping if bleach fails
                sanitized = html.escape(sanitized)
        
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'javascript:', r'vbscript:', r'data:', r'file:', r'ftp:',
            r'<script', r'</script>', r'on\w+\s*=', r'expression\s*\(',
            r'url\s*\(', r'import\s+', r'@import', r'<iframe', r'</iframe>'
        ]
        
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_url(url: str, allowed_domains: List[str] = None) -> str:
        """Sanitize and validate URLs
        
        Args:
            url: URL to sanitize
            allowed_domains: List of allowed domains (optional)
            
        Returns:
            Sanitized URL or empty string if invalid
        """
        if not url or not isinstance(url, str):
            return ""
        
        try:
            # Parse URL
            parsed = urlparse(url.strip())
            
            # Validate scheme
            if parsed.scheme not in ['http', 'https']:
                return ""
            
            # Validate domain if restrictions apply
            if allowed_domains:
                domain = parsed.netloc.lower()
                if not any(allowed_domain in domain for allowed_domain in allowed_domains):
                    return ""
            
            # Reconstruct safe URL
            safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                safe_url += f"?{parsed.query}"
            if parsed.fragment:
                safe_url += f"#{parsed.fragment}"
            
            return safe_url
            
        except Exception:
            return ""
    
    @staticmethod
    def sanitize_file_path(file_path: str) -> str:
        """Sanitize file paths to prevent directory traversal attacks
        
        Args:
            file_path: File path to sanitize
            
        Returns:
            Sanitized file path
        """
        if not file_path or not isinstance(file_path, str):
            return ""
        
        # Remove null bytes and normalize path
        sanitized = file_path.replace('\x00', '').replace('\\', '/')
        
        # Remove directory traversal attempts
        dangerous_patterns = [
            r'\.\./', r'\.\.\\', r'//', r'\\', r'~', r'%2e%2e', r'%2e%2e%2f'
        ]
        
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Remove leading slashes and normalize
        sanitized = sanitized.lstrip('/').lstrip('\\')
        
        return sanitized
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """Validate UUID format"""
        if not uuid_string or not isinstance(uuid_string, str):
            return False
            
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(uuid_string))
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format with additional security checks"""
        if not email or not isinstance(email, str):
            return False
            
        # Basic email pattern
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        
        if not email_pattern.match(email):
            return False
        
        # Additional security checks
        email_lower = email.lower()
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'\.\.', r'\.\.\.', r'\.\.\.\.',  # Multiple consecutive dots
            r'\.\.\.\.\.', r'\.\.\.\.\.\.', r'\.\.\.\.\.\.\.',
            r'\.\.\.\.\.\.\.\.', r'\.\.\.\.\.\.\.\.\.', r'\.\.\.\.\.\.\.\.\.\.'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, email_lower):
                return False
        
        # Check for excessive length
        if len(email) > 254:  # RFC 5321 limit
            return False
        
        # Check for excessive local part length
        local_part = email.split('@')[0]
        if len(local_part) > 64:  # RFC 5321 limit
            return False
        
        return True
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format with security checks"""
        if not phone or not isinstance(phone, str):
            return False
            
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Check if it's a valid length (7-15 digits)
        if not (7 <= len(digits_only) <= 15):
            return False
        
        # Check for suspicious patterns (repeated digits, sequential patterns)
        if len(set(digits_only)) <= 2:  # Too many repeated digits
            return False
        
        # Check for sequential patterns
        if len(digits_only) >= 3:
            for i in range(len(digits_only) - 2):
                if (int(digits_only[i+1]) == int(digits_only[i]) + 1 and 
                    int(digits_only[i+2]) == int(digits_only[i]) + 2):
                    return False
        
        return True
    
    @staticmethod
    def sanitize_json_data(data: Any, max_depth: int = 10) -> Any:
        """Recursively sanitize JSON data structures
        
        Args:
            data: Data to sanitize
            max_depth: Maximum recursion depth to prevent stack overflow
            
        Returns:
            Sanitized data
        """
        if max_depth <= 0:
            return None
        
        if isinstance(data, dict):
            return {
                AthleteUtils.sanitize_string(str(k), max_length=100): 
                AthleteUtils.sanitize_json_data(v, max_depth - 1)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [
                AthleteUtils.sanitize_json_data(item, max_depth - 1)
                for item in data
            ]
        elif isinstance(data, str):
            return AthleteUtils.sanitize_string(data)
        else:
            return data
    
    @staticmethod
    def validate_and_sanitize_input(input_data: Dict[str, Any], 
                                  required_fields: List[str] = None,
                                  optional_fields: List[str] = None,
                                  max_field_length: int = 1000) -> Dict[str, Any]:
        """Comprehensive input validation and sanitization
        
        Args:
            input_data: Input data to validate and sanitize
            required_fields: List of required fields
            optional_fields: List of optional fields
            max_field_length: Maximum length for string fields
            
        Returns:
            Sanitized input data
            
        Raises:
            ValueError: If validation fails
        """
        if not isinstance(input_data, dict):
            raise ValueError("Input data must be a dictionary")
        
        # Check required fields
        if required_fields:
            for field in required_fields:
                if field not in input_data or input_data[field] is None:
                    raise ValueError(f"Required field '{field}' is missing")
        
        # Sanitize all fields
        sanitized_data = {}
        all_fields = set(input_data.keys())
        if required_fields:
            all_fields.update(required_fields)
        if optional_fields:
            all_fields.update(optional_fields)
        
        for field in all_fields:
            if field in input_data and input_data[field] is not None:
                value = input_data[field]
                
                if isinstance(value, str):
                    sanitized_data[field] = AthleteUtils.sanitize_string(value, max_field_length)
                elif isinstance(value, (dict, list)):
                    sanitized_data[field] = AthleteUtils.sanitize_json_data(value)
                else:
                    sanitized_data[field] = value
        
        return sanitized_data 