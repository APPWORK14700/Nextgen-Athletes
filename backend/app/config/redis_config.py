"""
Redis Configuration for Athletes Networking App

This module provides Redis configuration and connection management.
"""

import os
from typing import Optional


class RedisConfig:
    """Redis configuration settings"""
    
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.db = int(os.getenv('REDIS_DB', 0))
        self.password = os.getenv('REDIS_PASSWORD')
        self.ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
        self.ssl_cert_reqs = os.getenv('REDIS_SSL_CERT_REQS', 'required')
        self.connection_pool_size = int(os.getenv('REDIS_POOL_SIZE', 10))
        self.socket_timeout = int(os.getenv('REDIS_SOCKET_TIMEOUT', 5))
        self.socket_connect_timeout = int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 5))
        self.retry_on_timeout = os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true'
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', 50))
    
    def get_connection_kwargs(self) -> dict:
        """Get connection parameters for Redis client"""
        kwargs = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'decode_responses': True,
            'socket_timeout': self.socket_timeout,
            'socket_connect_timeout': self.socket_connect_timeout,
            'retry_on_timeout': self.retry_on_timeout,
            'max_connections': self.max_connections
        }
        
        if self.password:
            kwargs['password'] = self.password
        
        if self.ssl:
            kwargs['ssl'] = self.ssl
            kwargs['ssl_cert_reqs'] = self.ssl_cert_reqs
        
        return kwargs
    
    def is_available(self) -> bool:
        """Check if Redis configuration is available"""
        return bool(self.host and self.port)
    
    def get_url(self) -> str:
        """Get Redis connection URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        else:
            return f"redis://{self.host}:{self.port}/{self.db}"


# Global Redis configuration instance
redis_config = RedisConfig()


def get_redis_config() -> RedisConfig:
    """Get global Redis configuration"""
    return redis_config 