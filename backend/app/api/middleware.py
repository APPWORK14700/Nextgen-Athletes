"""
Middleware for the Athletes Networking App API
"""

import time
import logging
import json
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..config.security_config import get_global_security_config
from ..utils.athlete_utils import AthleteUtils
from ..services.rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for comprehensive protection"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_config = get_global_security_config()
        self.rate_limit_service = RateLimitService()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security middleware"""
        start_time = time.time()
        
        try:
            # Apply security checks
            await self._apply_security_checks(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response = await self._add_security_headers(response)
            
            # Log request
            await self._log_request(request, response, start_time)
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            
            # Return generic error response in production
            if self.security_config.is_production():
                return JSONResponse(
                    status_code=500,
                    content={"error": "Internal server error"}
                )
            else:
                # In development, return detailed error
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )
    
    async def _apply_security_checks(self, request: Request) -> None:
        """Apply comprehensive security checks"""
        # Rate limiting
        if self.security_config.enable_rate_limiting:
            await self._check_rate_limit(request)
        
        # Request size validation
        await self._validate_request_size(request)
        
        # Input sanitization for query parameters
        await self._sanitize_query_params(request)
        
        # Block suspicious requests
        await self._check_suspicious_patterns(request)
    
    async def _check_rate_limit(self, request: Request) -> None:
        """Check rate limiting using centralized service"""
        client_ip = self._get_client_ip(request)
        endpoint = f"{request.method}:{request.url.path}"
        
        # Check rate limit using the centralized service
        rate_limit_result = await self.rate_limit_service.check_rate_limit(
            client_ip, endpoint
        )
        
        if not rate_limit_result['allowed']:
            logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
            
            # Add rate limit headers to response
            headers = {
                'X-RateLimit-Limit': str(rate_limit_result['limit']),
                'X-RateLimit-Remaining': str(rate_limit_result['remaining']),
                'X-RateLimit-Reset': str(rate_limit_result['reset_time']),
                'Retry-After': str(rate_limit_result['retry_after'])
            }
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": rate_limit_result['description'],
                    "retry_after": rate_limit_result['retry_after'],
                    "reset_time": rate_limit_result['reset_time']
                },
                headers=headers
            )
    
    async def _validate_request_size(self, request: Request) -> None:
        """Validate request size"""
        content_length = request.headers.get('content-length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > self.security_config.max_request_size_mb:
                raise HTTPException(
                    status_code=413,
                    detail=f"Request too large. Maximum size is {self.security_config.max_request_size_mb}MB"
                )
    
    async def _sanitize_query_params(self, request: Request) -> None:
        """Sanitize query parameters to prevent injection attacks"""
        query_params = dict(request.query_params)
        
        for key, value in query_params.items():
            if isinstance(value, str):
                # Sanitize string values
                sanitized_value = AthleteUtils.sanitize_string(value, max_length=200)
                if sanitized_value != value:
                    logger.warning(f"Sanitized query parameter {key}: {value} -> {sanitized_value}")
                    query_params[key] = sanitized_value
        
        # Update request with sanitized params
        request._query_params = query_params
    
    async def _check_suspicious_patterns(self, request: Request) -> None:
        """Check for suspicious request patterns"""
        url = str(request.url)
        user_agent = request.headers.get('user-agent', '')
        
        # Check for suspicious patterns in URL
        suspicious_patterns = [
            r'\.\.', r'\.\.\.', r'\.\.\.\.',  # Directory traversal
            r'<script', r'</script>',  # Script tags
            r'javascript:', r'vbscript:',  # Script protocols
            r'data:', r'file:', r'ftp:',  # Dangerous protocols
            r'--', r'/\*', r'\*/',  # SQL injection patterns
            r'<', r'>', r'"', r"'", r'&',  # HTML/XML injection
        ]
        
        for pattern in suspicious_patterns:
            if pattern in url.lower():
                logger.warning(f"Suspicious pattern detected in URL: {pattern}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid request pattern detected"
                )
        
        # Check for suspicious user agents
        suspicious_user_agents = [
            'sqlmap', 'nikto', 'nmap', 'wget', 'curl', 'python-requests'
        ]
        
        for suspicious_ua in suspicious_user_agents:
            if suspicious_ua.lower() in user_agent.lower():
                logger.warning(f"Suspicious user agent detected: {user_agent}")
                # Log but don't block - some legitimate tools use these
    
    async def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        security_headers = self.security_config.get_security_headers()
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add additional security headers
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
    
    async def _log_request(self, request: Request, response: Response, start_time: float) -> None:
        """Log request details for security monitoring"""
        if not self.security_config.log_sensitive_operations:
            return
        
        duration = time.time() - start_time
        client_ip = self._get_client_ip(request)
        
        # Log security-relevant information
        log_data = {
            'timestamp': time.time(),
            'client_ip': client_ip,
            'method': request.method,
            'url': str(request.url),
            'status_code': response.status_code,
            'duration': duration,
            'user_agent': request.headers.get('user-agent', ''),
            'content_length': request.headers.get('content-length', 0)
        }
        
        # Log suspicious requests
        if response.status_code >= 400:
            logger.warning(f"Security event: {json.dumps(log_data)}")
        else:
            logger.info(f"Request processed: {json.dumps(log_data)}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers (when behind proxy)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else 'unknown'


class CORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware with security configuration"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_config = get_global_security_config()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through CORS middleware"""
        # Handle preflight requests
        if request.method == 'OPTIONS':
            return await self._handle_preflight(request)
        
        # Process request
        response = await call_next(request)
        
        # Add CORS headers
        response = await self._add_cors_headers(request, response)
        
        return response
    
    async def _handle_preflight(self, request: Request) -> Response:
        """Handle CORS preflight requests"""
        origin = request.headers.get('origin')
        
        if not self._is_origin_allowed(origin):
            return JSONResponse(
                status_code=403,
                content={"error": "Origin not allowed"}
            )
        
        # Return preflight response
        response = JSONResponse(content={})
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Max-Age'] = '3600'
        
        return response
    
    async def _add_cors_headers(self, request: Request, response: Response) -> Response:
        """Add CORS headers to response"""
        origin = request.headers.get('origin')
        
        if self._is_origin_allowed(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        return response
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed"""
        if not origin:
            return False
        
        allowed_origins = self.security_config.allowed_origins
        return origin in allowed_origins


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware for audit purposes"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_config = get_global_security_config()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through logging middleware"""
        start_time = time.time()
        
        # Log request start
        await self._log_request_start(request)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log request completion
            await self._log_request_completion(request, response, start_time)
            
            return response
            
        except Exception as e:
            # Log request error
            await self._log_request_error(request, e, start_time)
            raise
    
    async def _log_request_start(self, request: Request) -> None:
        """Log request start"""
        if not self.security_config.enable_audit_logging:
            return
        
        client_ip = self._get_client_ip(request)
        logger.info(f"Request started: {request.method} {request.url} from {client_ip}")
    
    async def _log_request_completion(self, request: Request, response: Response, start_time: float) -> None:
        """Log request completion"""
        if not self.security_config.enable_audit_logging:
            return
        
        duration = time.time() - start_time
        client_ip = self._get_client_ip(request)
        
        logger.info(
            f"Request completed: {request.method} {request.url} from {client_ip} "
            f"-> {response.status_code} in {duration:.3f}s"
        )
    
    async def _log_request_error(self, request: Request, error: Exception, start_time: float) -> None:
        """Log request error"""
        if not self.security_config.enable_audit_logging:
            return
        
        duration = time.time() - start_time
        client_ip = self._get_client_ip(request)
        
        logger.error(
            f"Request failed: {request.method} {request.url} from {client_ip} "
            f"-> {type(error).__name__}: {error} in {duration:.3f}s"
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown' 