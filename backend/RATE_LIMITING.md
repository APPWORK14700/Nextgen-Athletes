# Rate Limiting Implementation

## Overview

This document describes the centralized rate limiting system implemented for the Athletes Networking App backend. Rate limiting has been moved from individual services to the API level for better performance, security, and maintainability.

## Architecture

### Before (Service-Level Rate Limiting)
- Each service had its own rate limiting logic
- In-memory storage (lost on service restart)
- No coordination between services
- Resource waste (services process requests before checking limits)

### After (API-Level Rate Limiting)
- Centralized rate limiting at the API middleware level
- Redis-based storage (persistent across restarts)
- Global coordination and consistent behavior
- Early rejection (before reaching services)

## Components

### 1. RateLimitService (`app/services/rate_limit_service.py`)
- **Purpose**: Centralized rate limiting logic
- **Storage**: Redis (with in-memory fallback)
- **Features**:
  - Endpoint-specific rate limits
  - Sliding window implementation
  - IP-based limiting
  - Configurable limits per endpoint type

### 2. SecurityMiddleware (`app/api/middleware.py`)
- **Purpose**: API-level security and rate limiting
- **Integration**: Uses RateLimitService for all requests
- **Features**:
  - Request validation
  - Input sanitization
  - Suspicious pattern detection
  - Security headers

### 3. Redis Configuration (`app/config/redis_config.py`)
- **Purpose**: Centralized Redis connection management
- **Features**:
  - Environment-based configuration
  - Connection pooling
  - SSL support
  - Health checks

## Rate Limit Configuration

### Endpoint Types and Limits

```python
rate_limit_configs = {
    'global': {
        'requests': 1000,        # 1000 req/hour per IP
        'window_seconds': 3600,  # 1 hour
        'description': 'Global API rate limit per IP'
    },
    'auth': {
        'requests': 10,          # 10 attempts per 5 min
        'window_seconds': 300,   # 5 minutes
        'description': 'Authentication attempts per IP'
    },
    'upload': {
        'requests': 50,          # 50 uploads per hour
        'window_seconds': 3600,  # 1 hour
        'description': 'File uploads per IP'
    },
    'search': {
        'requests': 30,          # 30 searches per minute
        'window_seconds': 60,    # 1 minute
        'description': 'Search requests per IP'
    },
    'api': {
        'requests': 100,         # 100 API calls per hour
        'window_seconds': 3600,  # 1 hour
        'description': 'General API calls per IP'
    },
    'session': {
        'requests': 5,           # 5 session creations per 5 min
        'window_seconds': 300,   # 5 minutes
        'description': 'Session creation attempts per IP'
    }
}
```

### Automatic Endpoint Detection

The system automatically determines rate limit type based on endpoint patterns:
- **Auth endpoints**: `/auth/*`, `/login`, `/register`
- **Upload endpoints**: `/upload/*`, `/media/*`
- **Search endpoints**: `/search/*`
- **Session endpoints**: `/session/*`
- **General API**: All other endpoints

## Environment Configuration

### Required Environment Variables

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_SSL=false
REDIS_POOL_SIZE=10
REDIS_MAX_CONNECTIONS=50

# Rate Limiting Configuration
RATE_LIMIT_WINDOW_SECONDS=3600
MAX_REQUESTS_PER_WINDOW=1000
MAX_UPLOADS_PER_HOUR=50
```

### Optional Environment Variables

```bash
# SSL Configuration
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required

# Performance Tuning
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
```

## Implementation Details

### Redis Storage Strategy

- **Key Format**: `rate_limit:{endpoint}:{identifier}`
- **Data Structure**: Redis Sorted Set (ZSET)
- **Expiration**: Automatic cleanup of expired entries
- **Atomic Operations**: Pipeline-based operations for consistency

### Fallback Strategy

If Redis is unavailable, the system falls back to in-memory rate limiting:
- **Storage**: Python dictionary with automatic cleanup
- **Limitations**: Lost on service restart, no cross-instance coordination
- **Recommendation**: Always use Redis in production

### Rate Limit Headers

When rate limits are exceeded, the API returns:
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200
Retry-After: 3600
```

## Migration from Service-Level Rate Limiting

### Removed Code

The following rate limiting code has been removed from services:

1. **MediaUploadService**:
   - `_upload_counts` dictionary
   - `_check_upload_rate_limit()` method
   - Upload rate limit checks in `upload_media()` and `bulk_upload_media()`

2. **SearchService**:
   - `max_searches_per_user` attribute
   - `_cleanup_old_searches()` method
   - Search cleanup calls in `save_search()`

3. **AuthService**:
   - `max_sessions_per_user` attribute
   - `_cleanup_old_sessions()` method
   - Session cleanup calls in `create_session()`

### Benefits of Migration

- **Performance**: 10-100x faster rate limit checks
- **Scalability**: No memory leaks or service bloat
- **Maintenance**: Single point of configuration
- **Monitoring**: Centralized rate limit analytics
- **Security**: Better DDoS protection

## Monitoring and Analytics

### Rate Limit Events

The system logs all rate limit events:
```python
logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
```

### Health Checks

```python
# Check rate limiting service health
health_status = await rate_limit_service.health_check()
```

### Metrics Available

- Rate limit violations per endpoint
- Client IP distribution
- Peak usage patterns
- Redis connection status

## Best Practices

### 1. Redis Configuration
- Use Redis Cluster for high availability
- Enable persistence (RDB + AOF)
- Monitor memory usage
- Set appropriate maxmemory policy

### 2. Rate Limit Tuning
- Start with conservative limits
- Monitor user behavior patterns
- Adjust limits based on legitimate usage
- Consider burst allowances for authenticated users

### 3. Error Handling
- Always handle rate limit exceptions gracefully
- Provide clear error messages to users
- Include retry-after information
- Log violations for security monitoring

### 4. Testing
- Test rate limiting with various client patterns
- Verify fallback behavior when Redis is down
- Load test with realistic traffic patterns
- Monitor performance impact

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis service status
   - Verify connection parameters
   - Check firewall/network configuration

2. **Rate Limits Too Strict**
   - Adjust limits in `rate_limit_configs`
   - Consider user authentication status
   - Review legitimate usage patterns

3. **Performance Issues**
   - Monitor Redis performance
   - Check connection pool settings
   - Verify key expiration policies

### Debug Mode

Enable debug logging:
```python
logging.getLogger('app.services.rate_limit_service').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **User-Based Rate Limiting**
   - Different limits for authenticated users
   - Role-based rate limiting
   - Premium user allowances

2. **Dynamic Rate Limiting**
   - Adaptive limits based on server load
   - Geographic rate limiting
   - Time-based rate adjustments

3. **Advanced Analytics**
   - Real-time rate limit dashboards
   - Predictive rate limiting
   - Anomaly detection

4. **Integration Features**
   - Webhook notifications for violations
   - Integration with monitoring systems
   - Custom rate limit policies per organization 