"""
Test file for refactored AthleteService with PerformanceMonitor integration
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from app.services.athlete_service import AthleteService, AthleteServiceConfig
from app.models.athlete import AthleteProfileCreate, AthleteProfileUpdate, AthleteSearchFilters
from app.services.exceptions import AthleteServiceError
from app.utils.performance_monitor import PerformanceMonitor


class TestAthleteService:
    """Test cases for refactored AthleteService"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'collections': {
                'athlete_profiles': 'athlete_profiles',
                'users': 'users',
                'media': 'media'
            },
            'search_limits': {
                'max_limit': 100
            },
            'bulk_limits': {
                'max_bulk_update': 1000
            },
            'statistics_limits': {
                'max_sample_size': 1000
            },
            'performance': {
                'enable_caching': True
            },
            'age_limits': {
                'min_age': 13,
                'max_age': 100
            }
        }
    
    @pytest.fixture
    def mock_profile_service(self):
        """Mock profile service"""
        mock_service = Mock()
        mock_service.create_athlete_profile = AsyncMock(return_value={'id': '1', 'name': 'John'})
        mock_service.get_athlete_profile = AsyncMock(return_value={'id': '1', 'name': 'John'})
        mock_service.update_athlete_profile = AsyncMock(return_value={'id': '1', 'name': 'John Updated'})
        mock_service.delete_athlete_profile = AsyncMock(return_value=True)
        mock_service.restore_athlete_profile = AsyncMock(return_value=True)
        mock_service.get_athlete_profile_completion = AsyncMock(return_value={'completion': 85})
        return mock_service
    
    @pytest.fixture
    def mock_search_service(self):
        """Mock search service"""
        mock_service = Mock()
        mock_service.search_athletes = AsyncMock(return_value=Mock(count=1, results=[{'id': '1'}]))
        mock_service.get_athletes_by_sport_category = AsyncMock(return_value=Mock(count=1, results=[{'id': '1'}]))
        mock_service.get_athletes_by_location = AsyncMock(return_value=Mock(count=1, results=[{'id': '1'}]))
        mock_service.get_athletes_by_age_range = AsyncMock(return_value=Mock(count=1, results=[{'id': '1'}]))
        mock_service.get_active_athletes_count = AsyncMock(return_value=100)
        return mock_service
    
    @pytest.fixture
    def mock_recommendation_service(self):
        """Mock recommendation service"""
        mock_service = Mock()
        mock_service.get_recommended_athletes = AsyncMock(return_value=[{'id': '1', 'name': 'John'}])
        mock_service.get_athletes_by_preferences = AsyncMock(return_value=[{'id': '1', 'name': 'John'}])
        mock_service.get_similar_athletes = AsyncMock(return_value=[{'id': '2', 'name': 'Jane'}])
        return mock_service
    
    @pytest.fixture
    def mock_analytics_service(self):
        """Mock analytics service"""
        mock_service = Mock()
        mock_service.get_athlete_analytics = AsyncMock(return_value=Mock(profile_views=10))
        mock_service.get_athlete_statistics = AsyncMock(return_value={'total_athletes': 100})
        mock_service.bulk_update_athletes = AsyncMock(return_value={'updated': 5})
        mock_service.get_athlete_media = AsyncMock(return_value=[{'id': '1', 'type': 'image'}])
        mock_service.get_athlete_stats = AsyncMock(return_value=[{'id': '1', 'stat': '100m'}])
        mock_service.get_active_athletes_count = AsyncMock(return_value=100)
        return mock_service
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_init_with_performance_monitor(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test service initialization with PerformanceMonitor"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        assert service.config == mock_config
        assert isinstance(service.performance_monitor, PerformanceMonitor)
        assert service.profile_service is not None
        assert service.search_service is not None
        assert service.recommendation_service is not None
        assert service.analytics_service is not None
    
    @patch('app.services.athlete_service.get_athlete_config')
    def test_init_with_missing_config(self, mock_get_config):
        """Test service initialization with missing configuration"""
        mock_get_config.return_value = {'collections': {}}
        
        with pytest.raises(ValueError, match="Missing required configuration keys"):
            AthleteService()
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_performance_monitor_threshold_configuration(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test PerformanceMonitor is configured with correct thresholds"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Check that PerformanceMonitor is initialized with the maximum threshold
        max_threshold = max(AthleteServiceConfig.SLOW_OPERATION_THRESHOLDS.values())
        assert service.performance_monitor.threshold_ms == max_threshold
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_get_performance_metrics(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test performance metrics retrieval"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Mock the performance monitor methods
        service.performance_monitor.get_metrics = Mock(return_value={'test': 'metrics'})
        service.performance_monitor.get_slow_operations = Mock(return_value={'slow': 'ops'})
        service.performance_monitor.generate_report = Mock(return_value='Performance Report')
        
        metrics = service.get_performance_metrics()
        
        assert 'performance_monitor_metrics' in metrics
        assert 'slow_operations' in metrics
        assert 'performance_report' in metrics
        assert metrics['performance_monitor_metrics'] == {'test': 'metrics'}
        assert metrics['slow_operations'] == {'slow': 'ops'}
        assert metrics['performance_report'] == 'Performance Report'
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    @pytest.mark.asyncio
    async def test_profile_operations_with_performance_monitoring(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test profile operations with PerformanceMonitor integration"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = mock_profile_service()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Test profile creation
        profile_data = AthleteProfileCreate(
            first_name="John",
            last_name="Doe",
            date_of_birth=datetime(2000, 1, 1).date(),
            gender="male",
            location="NYC",
            primary_sport_category_id="football",
            position="forward",
            height_cm=180,
            weight_kg=75
        )
        
        result = await service.create_athlete_profile("user123", profile_data)
        assert result['id'] == '1'
        assert result['name'] == 'John'
        
        # Verify PerformanceMonitor has metrics for this operation
        metrics = service.performance_monitor.get_metrics()
        assert 'profile_creation' in metrics
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    @pytest.mark.asyncio
    async def test_search_operations_with_performance_monitoring(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test search operations with PerformanceMonitor integration"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = mock_search_service()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Test search athletes
        filters = AthleteSearchFilters(limit=20, offset=0)
        result = await service.search_athletes(filters)
        assert result.count == 1
        
        # Test get athletes by sport category
        result = await service.get_athletes_by_sport_category("football", limit=10)
        assert result.count == 1
        
        # Verify PerformanceMonitor has metrics for these operations
        metrics = service.performance_monitor.get_metrics()
        assert 'search_operation' in metrics
        assert 'sport_category_query' in metrics
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    @pytest.mark.asyncio
    async def test_recommendation_operations_with_performance_monitoring(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test recommendation operations with PerformanceMonitor integration"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = mock_recommendation_service()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Test get recommended athletes
        result = await service.get_recommended_athletes("scout123", limit=10)
        assert len(result) == 1
        assert result[0]['name'] == 'John'
        
        # Test get athletes by preferences
        preferences = {'sport': 'football', 'position': 'forward'}
        result = await service.get_athletes_by_preferences(preferences, limit=10)
        assert len(result) == 1
        
        # Verify PerformanceMonitor has metrics for these operations
        metrics = service.performance_monitor.get_metrics()
        assert 'recommendation_query' in metrics
        assert 'preference_query' in metrics
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    @pytest.mark.asyncio
    async def test_analytics_operations_with_performance_monitoring(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test analytics operations with PerformanceMonitor integration"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = mock_analytics_service()
        
        service = AthleteService()
        
        # Test get athlete analytics
        result = await service.get_athlete_analytics("athlete123")
        assert result.profile_views == 10
        
        # Test get athlete statistics
        result = await service.get_athlete_statistics()
        assert result['total_athletes'] == 100
        
        # Test bulk update
        updates = [{'id': '1', 'update': 'data'}]
        result = await service.bulk_update_athletes(updates)
        assert result['updated'] == 5
        
        # Verify PerformanceMonitor has metrics for these operations
        metrics = service.performance_monitor.get_metrics()
        assert 'analytics_query' in metrics
        assert 'statistics_query' in metrics
        assert 'bulk_operation' in metrics
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_service_config(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test service configuration retrieval"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        config = service.get_service_config()
        
        assert config['environment'] == 'production'  # Since enable_caching is True
        assert 'profile_service' in config['services']
        assert 'search_service' in config['services']
        assert 'recommendation_service' in config['services']
        assert 'analytics_service' in config['services']
        assert 'performance' in config
        assert 'limits' in config
        assert 'thresholds' in config
        assert 'default_limits' in config
        assert config['thresholds'] == AthleteServiceConfig.SLOW_OPERATION_THRESHOLDS
        assert config['default_limits'] == AthleteServiceConfig.DEFAULT_LIMITS
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test health check functionality"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = mock_profile_service()
        mock_search.return_value = mock_search_service()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = mock_analytics_service()
        
        service = AthleteService()
        
        health = await service.health_check()
        
        assert 'status' in health
        assert 'timestamp' in health
        assert 'services' in health
        assert 'profile_service' in health['services']
        assert 'search_service' in health['services']
        assert 'recommendation_service' in health['services']
        assert 'analytics_service' in health['services']
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_validation_decorators(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test validation decorators still work correctly"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Test user_id validation
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            service.create_athlete_profile("", AthleteProfileCreate(
                first_name="John",
                last_name="Doe",
                date_of_birth=datetime(2000, 1, 1).date(),
                gender="male",
                location="NYC",
                primary_sport_category_id="football",
                position="forward",
                height_cm=180,
                weight_kg=75
            ))
        
        # Test athlete_id validation
        with pytest.raises(ValueError, match="athlete_id cannot be empty"):
            service.get_athlete_by_id("")
        
        # Test pagination validation
        with pytest.raises(ValueError, match="limit must be between 1 and 100"):
            service.get_athletes_by_sport_category("football", limit=0)
        
        with pytest.raises(ValueError, match="offset cannot be negative"):
            service.get_athletes_by_sport_category("football", offset=-1)
        
        # Test age range validation
        with pytest.raises(ValueError, match="min_age cannot be greater than max_age"):
            service.get_athletes_by_age_range(25, 20)
        
        # Test bulk operations validation
        with pytest.raises(ValueError, match="updates list cannot be empty"):
            service.bulk_update_athletes([])
        
        # Test preferences validation
        with pytest.raises(ValueError, match="preferences cannot be empty"):
            service.get_athletes_by_preferences({})
        
        # Test filters validation
        with pytest.raises(ValueError, match="filters cannot be None"):
            service.search_athletes(None)
    
    @patch('app.services.athlete_service.get_athlete_config')
    @patch('app.services.athlete_service.AthleteProfileService')
    @patch('app.services.athlete_service.AthleteSearchService')
    @patch('app.services.athlete_service.AthleteRecommendationService')
    @patch('app.services.athlete_service.AthleteAnalyticsService')
    def test_performance_monitor_integration(self, mock_analytics, mock_recommendation, mock_search, mock_profile, mock_get_config, mock_config):
        """Test that PerformanceMonitor is properly integrated and accessible"""
        mock_get_config.return_value = mock_config
        mock_profile.return_value = Mock()
        mock_search.return_value = Mock()
        mock_recommendation.return_value = Mock()
        mock_analytics.return_value = Mock()
        
        service = AthleteService()
        
        # Verify PerformanceMonitor instance exists and has expected methods
        assert hasattr(service.performance_monitor, 'get_metrics')
        assert hasattr(service.performance_monitor, 'get_slow_operations')
        assert hasattr(service.performance_monitor, 'generate_report')
        assert hasattr(service.performance_monitor, 'reset_metrics')
        
        # Test that metrics start empty
        initial_metrics = service.performance_monitor.get_metrics()
        assert initial_metrics == {}
        
        # Test that we can reset metrics
        service.performance_monitor.reset_metrics()
        reset_metrics = service.performance_monitor.get_metrics()
        assert reset_metrics == {}


if __name__ == "__main__":
    pytest.main([__file__]) 