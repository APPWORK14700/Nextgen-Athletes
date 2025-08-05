from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import time
from typing import Callable
import json

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, default_limits: str = "100/minute"):
        super().__init__(app)
        self.limiter = limiter
        self.default_limits = default_limits
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            # Apply rate limiting
            response = await call_next(request)
            
            # Add rate limit headers
            if hasattr(request.state, "rate_limit"):
                response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit.limit)
                response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit.remaining)
                response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit.reset)
            
            return response
            
        except RateLimitExceeded as e:
            return _rate_limit_exceeded_handler(request, e)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path} - Client: {request.client.host}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        # Add processing time header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Error handling middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Log error
            logger.error(f"Unhandled error in {request.method} {request.url.path}: {str(e)}")
            
            # Return error response
            error_response = {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {}
                }
            }
            
            return Response(
                content=json.dumps(error_response),
                status_code=500,
                media_type="application/json"
            )


def setup_middleware(app):
    """Setup all middleware"""
    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    
    return app 