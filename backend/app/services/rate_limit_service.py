"""
Rate limiting service for preventing abuse and implementing security measures
"""
import time
import asyncio
import logging
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_requests: int
    window_seconds: int
    block_duration_seconds: int = 300  # 5 minutes default block duration

class RateLimitExceededError(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after

class RateLimitService:
    """Service for managing rate limits across different operations"""
    
    def __init__(self):
        # In-memory storage for rate limits (in production, use Redis)
        self._rate_limits: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        self._blocked_ips: Dict[str, Tuple[datetime, int]] = {}
        self._lock = asyncio.Lock()
        
        # Default rate limit configurations
        self._default_configs = {
            "login": RateLimitConfig(max_requests=5, window_seconds=300),  # 5 attempts per 5 minutes
            "register": RateLimitConfig(max_requests=3, window_seconds=3600),  # 3 attempts per hour
            "password_reset": RateLimitConfig(max_requests=3, window_seconds=3600),  # 3 attempts per hour
            "search": RateLimitConfig(max_requests=100, window_seconds=3600),  # 100 searches per hour
            "report": RateLimitConfig(max_requests=5, window_seconds=86400),  # 5 reports per day
            "block": RateLimitConfig(max_requests=10, window_seconds=3600),  # 10 blocks per hour
            "profile_update": RateLimitConfig(max_requests=20, window_seconds=3600),  # 20 updates per hour
            "media_upload": RateLimitConfig(max_requests=50, window_seconds=3600),  # 50 uploads per hour
            "message": RateLimitConfig(max_requests=100, window_seconds=3600),  # 100 messages per hour
            "api_call": RateLimitConfig(max_requests=1000, window_seconds=3600),  # 1000 API calls per hour
        }
    
    async def check_rate_limit(self, key: str, operation: str = "api_call", 
                             custom_config: Optional[RateLimitConfig] = None) -> bool:
        """
        Check if a rate limit has been exceeded
        
        Args:
            key: Unique identifier (e.g., user_id, IP address)
            operation: Type of operation being rate limited
            custom_config: Custom rate limit configuration
            
        Returns:
            True if within rate limit, False if exceeded
            
        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        async with self._lock:
            # Check if IP is blocked
            if await self._is_ip_blocked(key):
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {operation}. Please try again later.",
                    retry_after=await self._get_block_remaining_time(key)
                )
            
            # Get configuration
            config = custom_config or self._default_configs.get(operation, self._default_configs["api_call"])
            
            # Get current timestamp
            now = time.time()
            
            # Clean old entries
            await self._cleanup_old_entries(key, operation, now, config.window_seconds)
            
            # Check if limit exceeded
            current_count = len(self._rate_limits[key][operation])
            
            if current_count >= config.max_requests:
                # Block the key temporarily
                await self._block_key(key, config.block_duration_seconds)
                
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {operation}. Maximum {config.max_requests} "
                    f"requests allowed per {config.window_seconds} seconds.",
                    retry_after=config.block_duration_seconds
                )
            
            # Record the request
            self._rate_limits[key][operation].append(now)
            
            return True
    
    async def record_request(self, key: str, operation: str = "api_call") -> None:
        """
        Record a request for rate limiting purposes
        
        Args:
            key: Unique identifier
            operation: Type of operation
        """
        async with self._lock:
            now = time.time()
            self._rate_limits[key][operation].append(now)
    
    async def get_remaining_requests(self, key: str, operation: str = "api_call") -> Tuple[int, int]:
        """
        Get remaining requests and reset time for a key
        
        Args:
            key: Unique identifier
            operation: Type of operation
            
        Returns:
            Tuple of (remaining_requests, seconds_until_reset)
        """
        async with self._lock:
            config = self._default_configs.get(operation, self._default_configs["api_call"])
            now = time.time()
            
            # Clean old entries
            await self._cleanup_old_entries(key, operation, now, config.window_seconds)
            
            current_count = len(self._rate_limits[key][operation])
            remaining = max(0, config.max_requests - current_count)
            
            # Calculate reset time
            if self._rate_limits[key][operation]:
                oldest_request = self._rate_limits[key][operation][0]
                reset_time = int(oldest_request + config.window_seconds - now)
            else:
                reset_time = 0
            
            return remaining, max(0, reset_time)
    
    async def reset_rate_limit(self, key: str, operation: str = "api_call") -> None:
        """
        Reset rate limit for a specific key and operation
        
        Args:
            key: Unique identifier
            operation: Type of operation
        """
        async with self._lock:
            if key in self._rate_limits and operation in self._rate_limits[key]:
                self._rate_limits[key][operation].clear()
    
    async def get_rate_limit_stats(self, key: str) -> Dict[str, Any]:
        """
        Get rate limit statistics for a key
        
        Args:
            key: Unique identifier
            
        Returns:
            Dictionary containing rate limit statistics
        """
        async with self._lock:
            stats = {}
            
            for operation, config in self._default_configs.items():
                remaining, reset_time = await self.get_remaining_requests(key, operation)
                stats[operation] = {
                    "remaining_requests": remaining,
                    "max_requests": config.max_requests,
                    "window_seconds": config.window_seconds,
                    "reset_in_seconds": reset_time,
                    "is_blocked": key in self._blocked_ips
                }
            
            return stats
    
    async def add_custom_rate_limit(self, operation: str, config: RateLimitConfig) -> None:
        """
        Add a custom rate limit configuration
        
        Args:
            operation: Operation name
            config: Rate limit configuration
        """
        async with self._lock:
            self._default_configs[operation] = config
    
    async def cleanup_expired_entries(self) -> int:
        """
        Clean up expired rate limit entries
        
        Returns:
            Number of cleaned entries
        """
        async with self._lock:
            cleaned_count = 0
            now = time.time()
            
            # Clean up rate limits
            for key in list(self._rate_limits.keys()):
                for operation in list(self._rate_limits[key].keys()):
                    config = self._default_configs.get(operation, self._default_configs["api_call"])
                    cleaned = await self._cleanup_old_entries(key, operation, now, config.window_seconds)
                    cleaned_count += cleaned
                    
                    # Remove empty operation entries
                    if not self._rate_limits[key][operation]:
                        del self._rate_limits[key][operation]
                
                # Remove empty key entries
                if not self._rate_limits[key]:
                    del self._rate_limits[key]
            
            # Clean up blocked IPs
            expired_blocks = [
                ip for ip, (block_time, duration) in self._blocked_ips.items()
                if now - block_time > duration
            ]
            
            for ip in expired_blocks:
                del self._blocked_ips[ip]
                cleaned_count += 1
            
            return cleaned_count
    
    async def _cleanup_old_entries(self, key: str, operation: str, 
                                 current_time: float, window_seconds: int) -> int:
        """Clean up old entries for a specific key and operation"""
        if key not in self._rate_limits or operation not in self._rate_limits[key]:
            return 0
        
        queue = self._rate_limits[key][operation]
        cutoff_time = current_time - window_seconds
        
        # Remove old entries
        cleaned_count = 0
        while queue and queue[0] < cutoff_time:
            queue.popleft()
            cleaned_count += 1
        
        return cleaned_count
    
    async def _is_ip_blocked(self, key: str) -> bool:
        """Check if a key is currently blocked"""
        if key not in self._blocked_ips:
            return False
        
        block_time, duration = self._blocked_ips[key]
        return time.time() - block_time < duration
    
    async def _block_key(self, key: str, duration_seconds: int) -> None:
        """Block a key for a specified duration"""
        self._blocked_ips[key] = (time.time(), duration_seconds)
        logger.warning(f"Rate limit exceeded for key {key}. Blocked for {duration_seconds} seconds.")
    
    async def _get_block_remaining_time(self, key: str) -> int:
        """Get remaining block time for a key"""
        if key not in self._blocked_ips:
            return 0
        
        block_time, duration = self._blocked_ips[key]
        remaining = duration - (time.time() - block_time)
        return max(0, int(remaining))

# Global rate limit service instance
rate_limit_service = RateLimitService()

# Convenience functions
async def check_rate_limit(key: str, operation: str = "api_call") -> bool:
    """Convenience function to check rate limit"""
    return await rate_limit_service.check_rate_limit(key, operation)

async def record_request(key: str, operation: str = "api_call") -> None:
    """Convenience function to record a request"""
    await rate_limit_service.record_request(key, operation)

async def get_remaining_requests(key: str, operation: str = "api_call") -> Tuple[int, int]:
    """Convenience function to get remaining requests"""
    return await rate_limit_service.get_remaining_requests(key, operation) 