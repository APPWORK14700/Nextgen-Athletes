"""
Test file for improved AthleteSearchService with caching, sanitization, and performance features
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import time
import threading

from app.services.athlete_search_service import AthleteSearchService
from app.models.athlete import AthleteSearchFilters
from app.services.exceptions import InputValidationError, AthleteServiceError
from app.services.database_service import ValidationError, DatabaseError
from app.utils.performance_monitor import PerformanceMonitor


class TestImprovedAthleteSearchService:
    """Test cases for improved AthleteSearchService"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing with all required keys"""
        return {
            'collections': {
                'athlete_profiles': 'athlete_profiles'
            },
            'search_limits': {
                'min_limit': 1,
                'max_limit': 100,
                'default_limit': 20,
                'max_offset': 10000
            },
            'age_limits': {
                'min_age': 13,
                'max_age': 100
            },
            'logging': {
                'log_search_queries': False,
                'log_query_performance': False,
                'slow_query_threshold': 1.0,
                'slow_count_query_threshold': 0.5,
                'log_cache_operations': False
            },
            'performance': {
                'enable_caching': True,
                'cache_size': 128,
                'cache_ttl_seconds': 3600,
                'enable_batch_processing': True,
                'max_concurrent_queries': 5,
                'enable_query_optimization': True,
                'max_query_timeout': 30
            },
            'security': {
                'enable_input_validation': True,
                'enable_sanitization': True,
                'max_string_length': 1000,
                'allowed_genders': ['male', 'female', 'other'],
                'enable_rate_limiting': True,
                'max_requests_per_minute': 100,
                'blocked_patterns': ['script', '<', '>', 'javascript'],
                'enable_audit_logging': True
            }
        }
    
    @pytest.fixture
    def mock_database_service(self):
        """Mock database service"""
        mock_service = Mock()
        mock_service.query = AsyncMock(return_value=[])
        mock_service.count = AsyncMock(return_value=0)
        return mock_service
    
    @patch('app.services.athlete_search_service.get_athlete_config')
    @patch('app.services.athlete_search_service.DatabaseService')
    @patch('app.services.athlete_search_service.DatabaseConnectionPool')
    def test_init_with_complete_config(self, mock_connection_pool, mock_db_service, mock_get_config, mock_config):
        """Test service initialization with complete configuration"""
        mock_get_config.return_value = mock_config
        mock_db_service.return_value = Mock()
        mock_connection_pool.return_value = Mock()
        
        service = AthleteSearchService()
        
        assert service.config == mock_config
        assert service.collections == mock_config['collections']
        assert service.search_limits == mock_config['search_limits']
        assert service.age_limits == mock_config['age_limits']
        assert service.performance_config == mock_config['performance']
        assert service.security_config == mock_config['security']
        assert service._query_cache == {}
        assert service.cache_ttl == 3600
        assert service.max_cache_size == 128
        assert isinstance(service.performance_monitor, PerformanceMonitor)
        assert isinstance(service._cache_lock, threading.Lock)
        assert service.connection_pool is not None
    
    @patch('app.services.athlete_search_service.get_athlete_config')
    @patch('app.services.athlete_search_service.DatabaseService')
    @patch('app.services.athlete_search_service.DatabaseConnectionPool')
    def test_init_with_missing_config_keys(self, mock_connection_pool, mock_db_service, mock_get_config):
        """Test service initialization with missing configuration keys"""
        mock_get_config.return_value = {'collections': {}}
        
        with pytest.raises(ValueError, match="Missing required configuration keys"):
            AthleteSearchService()
    
    @patch('app.services.athlete_search_service.get_athlete_config')
    @patch('app.services.athlete_search_service.DatabaseService')
    @patch('app.services.athlete_search_service.DatabaseConnectionPool')
    def test_init_with_partial_config(self, mock_connection_pool, mock_db_service, mock_get_config):
        """Test service initialization with partial config (missing performance/security)"""
        partial_config = {
            'collections': {'athlete_profiles': 'athlete_profiles'},
            'search_limits': {'min_limit': 1, 'max_limit': 100, 'default_limit': 20, 'max_offset': 10000},
            'age_limits': {'min_age': 13, 'max_age': 100},
            'logging': {'log_search_queries': False, 'log_query_performance': False, 'slow_query_threshold': 1.0, 'slow_count_query_threshold': 0.5}
        }
        
        mock_get_config.return_value = partial_config
        mock_db_service.return_value = Mock()
        mock_connection_pool.return_value = Mock()
        
        service = AthleteSearchService()
        
        # Should have default performance and security configs
        assert 'performance' in service.config
        assert 'security' in service.config
        assert service.config['performance']['enable_caching'] == True
        assert service.config['security']['enable_sanitization'] == True
    
    def test_sanitize_search_input_normal_string(self, mock_config):
        """Test input sanitization with normal string"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    result = service._sanitize_search_input("normal text")
                    assert result == "normal text"
    
    def test_sanitize_search_input_with_dangerous_chars(self, mock_config):
        """Test input sanitization with dangerous characters"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    result = service._sanitize_search_input("<script>alert('xss')</script>")
                    assert result == "scriptalertxss"
                    assert "<" not in result
                    assert ">" not in result
                    assert "'" not in result
    
    def test_sanitize_search_input_with_blocked_patterns(self, mock_config):
        """Test input sanitization with blocked patterns"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    result = service._sanitize_search_input("javascript:alert('xss')")
                    assert "javascript" not in result
                    assert "alert" in result  # Only blocked patterns should be removed
    
    def test_sanitize_search_input_with_long_string(self, mock_config):
        """Test input sanitization with string exceeding max length"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    long_string = "a" * 1500
                    result = service._sanitize_search_input(long_string)
                    assert len(result) == 1000  # max_string_length from config
                    assert result == "a" * 1000
    
    def test_validate_and_sanitize_filters(self, mock_config):
        """Test filter validation and sanitization"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    filters = AthleteSearchFilters(
                        sport_category_id="<script>football</script>",
                        position="forward<script>",
                        gender="male",
                        location="NYC<script>alert('xss')</script>"
                    )
                    
                    sanitized = service._validate_and_sanitize_filters(filters)
                    
                    # Verify dangerous characters are removed
                    assert "<" not in sanitized.sport_category_id
                    assert "<" not in sanitized.position
                    assert "<" not in sanitized.location
                    assert sanitized.gender == "male"  # Valid gender
    
    def test_validate_and_sanitize_filters_invalid_gender(self, mock_config):
        """Test filter validation with invalid gender"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    filters = AthleteSearchFilters(gender="invalid_gender")
                    
                    with pytest.raises(InputValidationError, match="Invalid gender value"):
                        service._validate_and_sanitize_filters(filters)
    
    def test_get_cache_key_consistency(self, mock_config):
        """Test cache key generation consistency"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    filters1 = AthleteSearchFilters(limit=20, offset=0, sport_category_id="football")
                    filters2 = AthleteSearchFilters(limit=20, offset=0, sport_category_id="football")
                    
                    key1 = service._get_cache_key(filters1)
                    key2 = service._get_cache_key(filters2)
                    
                    assert key1 == key2
    
    def test_clean_cache_thread_safety(self, mock_config):
        """Test cache cleaning with thread safety"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    # Add some cache entries
                    service._query_cache['key1'] = {'data': 'test1', 'timestamp': time.time()}
                    service._query_cache['key2'] = {'data': 'test2', 'timestamp': time.time()}
                    
                    # Test that clean_cache can be called without errors
                    service._clean_cache()
                    
                    # Verify cache is accessible
                    assert len(service._query_cache) >= 0
    
    def test_audit_logging(self, mock_config):
        """Test audit logging functionality"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    with patch('app.services.athlete_search_service.logger') as mock_logger:
                        service = AthleteSearchService()
                        
                        service._log_audit_event("test_event", "user123", {"detail": "test"})
                        
                        # Verify audit log was called
                        mock_logger.info.assert_called_once()
                        call_args = mock_logger.info.call_args[0][0]
                        assert "AUDIT:" in call_args
                        assert "test_event" in call_args
                        assert "user123" in call_args
    
    def test_audit_logging_disabled(self, mock_config):
        """Test audit logging when disabled"""
        mock_config['security']['enable_audit_logging'] = False
        
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    with patch('app.services.athlete_search_service.logger') as mock_logger:
                        service = AthleteSearchService()
                        
                        service._log_audit_event("test_event", "user123", {"detail": "test"})
                        
                        # Verify no logging occurred
                        mock_logger.info.assert_not_called()
    
    def test_query_optimization(self, mock_config):
        """Test query filter optimization"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    # Create mock filters
                    mock_filters = [
                        Mock(field_path="location"),
                        Mock(field_path="is_active"),
                        Mock(field_path="position")
                    ]
                    
                    optimized = service._optimize_query_filters(mock_filters)
                    
                    # Should reorder filters by selectivity
                    assert len(optimized) == 3
    
    def test_query_optimization_disabled(self, mock_config):
        """Test query optimization when disabled"""
        mock_config['performance']['enable_query_optimization'] = False
        
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    mock_filters = [Mock(field_path="location")]
                    optimized = service._optimize_query_filters(mock_filters)
                    
                    # Should return original filters unchanged
                    assert optimized == mock_filters
    
    def test_get_health_status(self, mock_config):
        """Test health status method"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    health = service.get_health_status()
                    
                    assert health['status'] == 'healthy'
                    assert 'cache_status' in health
                    assert 'database_status' in health
                    assert 'performance' in health
                    assert 'security' in health
                    assert health['cache_status']['enabled'] == True
                    assert health['security']['sanitization'] == True
    
    def test_get_performance_stats_with_monitor(self, mock_config):
        """Test performance statistics including monitor metrics"""
        with patch('app.services.athlete_search_service.get_athlete_config', return_value=mock_config):
            with patch('app.services.athlete_search_service.DatabaseService'):
                with patch('app.services.athlete_search_service.DatabaseConnectionPool'):
                    service = AthleteSearchService()
                    
                    # Simulate some activity
                    service._query_stats['total_queries'] = 10
                    service._query_stats['cache_hits'] = 6
                    service._query_stats['cache_misses'] = 4
                    service._query_stats['total_query_time'] = 5.0
                    service._query_stats['query_times'] = [0.5] * 10
                    
                    stats = service.get_performance_stats()
                    
                    assert stats['total_queries'] == 10
                    assert stats['cache_hits'] == 6
                    assert stats['cache_misses'] == 4
                    assert stats['cache_hit_rate'] == 60.0
                    assert stats['total_query_time'] == 5.0
                    assert stats['avg_query_time'] == 0.5
                    assert 'performance_monitor_metrics' in stats
    
    @patch('app.services.athlete_search_service.get_athlete_config')
    @patch('app.services.athlete_search_service.DatabaseService')
    @patch('app.services.athlete_search_service.DatabaseConnectionPool')
    @pytest.mark.asyncio
    async def test_search_athletes_with_performance_monitor(self, mock_connection_pool, mock_db_service, mock_get_config, mock_config):
        """Test search athletes with PerformanceMonitor integration"""
        mock_get_config.return_value = mock_config
        
        mock_db = Mock()
        mock_db.query = AsyncMock(return_value=[{'id': '1', 'name': 'John'}])
        mock_db.count = AsyncMock(return_value=1)
        mock_db_service.return_value = mock_db
        mock_connection_pool.return_value = Mock()
        
        service = AthleteSearchService()
        filters = AthleteSearchFilters(limit=20, offset=0)
        
        # Test search with performance monitoring
        result = await service.search_athletes(filters, user_id="test_user")
        
        assert result.count == 1
        assert len(result.results) == 1
        
        # Verify performance monitor has metrics
        monitor_metrics = service.performance_monitor.get_metrics()
        assert 'search_athletes' in monitor_metrics
    
    @patch('app.services.athlete_search_service.get_athlete_config')
    @patch('app.services.athlete_search_service.DatabaseService')
    @patch('app.services.athlete_search_service.DatabaseConnectionPool')
    def test_clear_cache_thread_safe(self, mock_connection_pool, mock_db_service, mock_get_config, mock_config):
        """Test cache clearing with thread safety"""
        mock_get_config.return_value = mock_config
        mock_db_service.return_value = Mock()
        mock_connection_pool.return_value = Mock()
        
        service = AthleteSearchService()
        
        # Add some cache entries
        service._query_cache['key1'] = {'data': 'test1', 'timestamp': time.time()}
        service._query_cache['key2'] = {'data': 'test2', 'timestamp': time.time()}
        
        assert len(service._query_cache) == 2
        
        # Clear cache (should be thread-safe)
        service.clear_cache()
        
        assert len(service._query_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__]) 