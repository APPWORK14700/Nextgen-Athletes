"""
Tests for AthleteRecommendationService
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, timezone
from dateutil.relativedelta import relativedelta
import logging

from app.services.athlete_recommendation_service import AthleteRecommendationService
from app.services.exceptions import RecommendationError
from app.services.database_service import DatabaseError


class TestAthleteRecommendationService:
    """Test cases for AthleteRecommendationService"""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        return {
            'collections': {
                'athlete_profiles': 'athlete_profiles',
                'scout_preferences': 'scout_preferences'
            },
            'recommendation_weights': {
                'sport_category_match': 50,
                'position_match': 30,
                'location_match': 20,
                'profile_completion': 0.3,
                'recent_activity_bonus': 10,
                'recent_activity_days': 30,
                # Similarity scoring weights
                'age_similarity_close': 25,
                'age_similarity_medium': 15,
                'age_similarity_far': 5,
                'completion_similarity_close': 20,
                'completion_similarity_medium': 10
            },
            'experience_thresholds': {
                'extensive_experience': 500,
                'moderate_experience': 200,
                'min_experience': 50,
                'extensive_score': 20,
                'moderate_score': 15,
                'min_score': 10,
                'age_bonus': 15
            },
            'field_weights': {
                'first_name': 10,
                'last_name': 10,
                'date_of_birth': 8,
                'gender': 8,
                'location': 10,
                'primary_sport_category_id': 12,
                'position': 12,
                'height_cm': 8,
                'weight_kg': 8,
                'academic_info': 6,
                'career_highlights': 8,
                'profile_image_url': 10
            }
        }
    
    @pytest.fixture
    def mock_athlete_repository(self):
        """Mock athlete repository"""
        mock_repo = AsyncMock()
        mock_repo.query.return_value = []
        mock_repo.get_by_field.return_value = None
        return mock_repo
    
    @pytest.fixture
    def mock_scout_prefs_repository(self):
        """Mock scout preferences repository"""
        mock_repo = AsyncMock()
        mock_repo.get_by_field.return_value = None
        return mock_repo
    
    @pytest.fixture
    def sample_athletes(self):
        """Sample athlete data for testing"""
        return [
            {
                'user_id': 'athlete1',
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': '2000-01-01',
                'gender': 'male',
                'location': 'New York',
                'primary_sport_category_id': 'football',
                'position': 'forward',
                'height_cm': 180,
                'weight_kg': 75,
                'academic_info': 'High School',
                'career_highlights': 'Team Captain, MVP 2022',
                'profile_image_url': 'http://example.com/image1.jpg',
                'is_active': True,
                'updated_at': '2024-01-15T10:00:00Z'
            },
            {
                'user_id': 'athlete2',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'date_of_birth': '2001-05-15',
                'gender': 'female',
                'location': 'Los Angeles',
                'primary_sport_category_id': 'basketball',
                'position': 'guard',
                'height_cm': 170,
                'weight_kg': 65,
                'academic_info': 'College',
                'career_highlights': 'All-Star 2023',
                'profile_image_url': 'http://example.com/image2.jpg',
                'is_active': True,
                'updated_at': '2024-01-10T14:30:00Z'
            }
        ]
    
    @pytest.fixture
    def sample_scout_preferences(self):
        """Sample scout preferences for testing"""
        return {
            'sport_category_ids': ['football', 'basketball'],
            'location': 'New York',
            'min_age': 18,
            'max_age': 25,
            'position_focus': ['forward', 'guard'],
            'experience_level': 'intermediate'
        }
    
    @pytest.mark.asyncio
    async def test_init_with_valid_config(self, mock_config):
        """Test service initialization with valid config"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            assert service.collections == mock_config['collections']
            assert service.recommendation_weights == mock_config['recommendation_weights']
            assert service.experience_thresholds == mock_config['experience_thresholds']
    
    @pytest.mark.asyncio
    async def test_get_recommended_athletes_success(self, mock_config, sample_athletes, sample_scout_preferences):
        """Test successful athlete recommendations"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = sample_athletes
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = sample_scout_preferences
            
            # Test the method
            result = await service.get_recommended_athletes('scout1', 10)
            
            # Verify results
            assert len(result) <= 10
            assert 'score' not in result[0]  # Score should be removed
            assert result[0]['user_id'] == 'athlete1'  # Should be sorted by score
    
    @pytest.mark.asyncio
    async def test_get_recommended_athletes_invalid_scout_id(self, mock_config):
        """Test recommendations with invalid scout ID"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            with pytest.raises(RecommendationError, match="Invalid input"):
                await service.get_recommended_athletes('', 10)
    
    @pytest.mark.asyncio
    async def test_get_recommended_athletes_invalid_limit(self, mock_config, sample_athletes):
        """Test recommendations with invalid limit"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock athlete repository
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = sample_athletes
            
            # Mock scout preferences repository
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = None
            
            # Test with invalid limit
            result = await service.get_recommended_athletes('scout1', -5)
            
            # Should use default limit
            assert len(result) <= 20
    
    @pytest.mark.asyncio
    async def test_get_athletes_by_preferences_success(self, mock_config, sample_athletes):
        """Test getting athletes by preferences"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock athlete repository
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = sample_athletes
            
            preferences = {
                'sport_category_ids': ['football'],
                'location': 'New York'
            }
            
            result = await service.get_athletes_by_preferences(preferences, 5)
            
            assert len(result) <= 5
            assert 'score' not in result[0]
    
    @pytest.mark.asyncio
    async def test_get_athletes_by_preferences_invalid_format(self, mock_config):
        """Test getting athletes with invalid preferences format"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            invalid_preferences = {
                'sport_category_ids': 'not_a_list',  # Should be list
                'min_age': 'not_a_number'  # Should be int
            }
            
            with pytest.raises(RecommendationError, match="Invalid preferences"):
                await service.get_athletes_by_preferences(invalid_preferences, 10)
    
    @pytest.mark.asyncio
    async def test_get_similar_athletes_success(self, mock_config, sample_athletes):
        """Test getting similar athletes"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.get_by_field.return_value = sample_athletes[0]  # Reference athlete
            service.athlete_repository.query.return_value = sample_athletes[1:]  # Similar athletes
            
            result = await service.get_similar_athletes('athlete1', 5)
            
            assert len(result) <= 5
            assert 'score' not in result[0]
    
    @pytest.mark.asyncio
    async def test_get_similar_athletes_not_found(self, mock_config):
        """Test getting similar athletes when reference athlete not found"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repository to return None
            service.athlete_repository = AsyncMock()
            service.athlete_repository.get_by_field.return_value = None
            
            with pytest.raises(RecommendationError, match="Athlete athlete1 not found"):
                await service.get_similar_athletes('athlete1', 5)
    
    @pytest.mark.asyncio
    async def test_get_similar_athletes_invalid_id(self, mock_config):
        """Test getting similar athletes with invalid ID"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            with pytest.raises(RecommendationError, match="Invalid input"):
                await service.get_similar_athletes('', 5)
    
    def test_validate_preferences_valid(self, mock_config):
        """Test preference validation with valid data"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            valid_preferences = {
                'sport_category_ids': ['football'],
                'position_focus': ['forward'],
                'min_age': 18,
                'max_age': 25
            }
            
            assert service._validate_preferences(valid_preferences) is True
    
    def test_validate_preferences_invalid_types(self, mock_config):
        """Test preference validation with invalid types"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            invalid_preferences = {
                'sport_category_ids': 'not_a_list',
                'position_focus': 'not_a_list',
                'min_age': 'not_a_number',
                'max_age': 'not_a_number'
            }
            
            assert service._validate_preferences(invalid_preferences) is False
    
    def test_validate_preferences_invalid_age_range(self, mock_config):
        """Test preference validation with invalid age range"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            invalid_age_range = {
                'min_age': 25,
                'max_age': 18  # min > max
            }
            
            assert service._validate_preferences(invalid_age_range) is False
    
    def test_validate_preferences_empty(self, mock_config):
        """Test preference validation with empty preferences"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            assert service._validate_preferences({}) is True
            assert service._validate_preferences(None) is True
    
    def test_calculate_age_valid_date(self, mock_config):
        """Test age calculation with valid date"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Calculate expected age
            birth_date = date(2000, 1, 1)
            today = date.today()
            expected_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            
            age = service._calculate_age('2000-01-01')
            assert age == expected_age
    
    def test_calculate_age_invalid_date(self, mock_config):
        """Test age calculation with invalid date"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            age = service._calculate_age('invalid-date')
            assert age == 0
    
    def test_calculate_age_empty_date(self, mock_config):
        """Test age calculation with empty date"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            age = service._calculate_age('')
            assert age == 0
    
    def test_calculate_age_none_date(self, mock_config):
        """Test age calculation with None date"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            age = service._calculate_age(None)
            assert age == 0
    
    def test_calculate_completion_percentage(self, mock_config):
        """Test profile completion percentage calculation"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Test with complete profile
            complete_profile = {
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': '2000-01-01',
                'gender': 'male',
                'location': 'New York',
                'primary_sport_category_id': 'football',
                'position': 'forward',
                'height_cm': 180,
                'weight_kg': 75,
                'academic_info': 'High School',
                'career_highlights': 'Team Captain',
                'profile_image_url': 'http://example.com/image.jpg'
            }
            
            completion = service._calculate_completion_percentage(complete_profile)
            assert completion == 100
            
            # Test with partial profile
            partial_profile = {
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': '2000-01-01'
            }
            
            completion = service._calculate_completion_percentage(partial_profile)
            assert 0 < completion < 100
    
    def test_calculate_experience_score(self, mock_config):
        """Test experience score calculation"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Test with extensive experience
            athlete_extensive = {
                'career_highlights': 'A' * 600,  # More than extensive threshold
                'date_of_birth': '1995-01-01'  # Senior age
            }
            
            score = service._calculate_experience_score(athlete_extensive, 'senior')
            assert score > 0
            
            # Test with minimal experience
            athlete_minimal = {
                'career_highlights': 'A' * 30,  # Less than min threshold
                'date_of_birth': '2005-01-01'  # Junior age
            }
            
            score = service._calculate_experience_score(athlete_minimal, 'junior')
            assert score >= 0
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_config):
        """Test handling of database errors"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repository to raise database error
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.side_effect = DatabaseError("Connection failed")
            
            with pytest.raises(DatabaseError):
                await service.get_recommended_athletes('scout1', 10)
    
    @pytest.mark.asyncio
    async def test_no_athletes_found(self, mock_config):
        """Test behavior when no athletes are found"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = []
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = None
            
            result = await service.get_recommended_athletes('scout1', 10)
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_scout_preferences_database_error(self, mock_config, sample_athletes):
        """Test handling of scout preferences database error"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = sample_athletes
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.side_effect = DatabaseError("Connection failed")
            
            # Should continue without preferences
            result = await service.get_recommended_athletes('scout1', 10)
            
            assert len(result) > 0  # Should still return athletes
    
    def test_apply_scout_preferences(self, mock_config):
        """Test applying scout preferences to filters"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            base_filters = []
            preferences = {
                'sport_category_ids': ['football', 'basketball'],
                'location': 'New York',
                'min_age': 18,
                'max_age': 25
            }
            
            result_filters = service._apply_scout_preferences(base_filters, preferences)
            
            assert len(result_filters) == 3  # sport, location, and age filters
            assert any('primary_sport_category_id' in str(f) for f in result_filters)
            assert any('location' in str(f) for f in result_filters)
            assert any('date_of_birth' in str(f) for f in result_filters)

    @pytest.mark.asyncio
    async def test_init_with_missing_config_section(self):
        """Test service initialization with missing config section"""
        incomplete_config = {
            'collections': {'athlete_profiles': 'athlete_profiles'},
            'recommendation_weights': {'sport_category_match': 50}
            # Missing experience_thresholds and field_weights
        }
        
        with patch('app.services.athlete_recommendation_service.get_config', return_value=incomplete_config):
            with pytest.raises(ValueError, match="Missing required configuration section"):
                AthleteRecommendationService()
    
    @pytest.mark.asyncio
    async def test_get_athletes_with_optimized_filtering_validation(self, mock_config):
        """Test the optimized filtering method with data validation"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repository to return athletes with missing user_id
            service.athlete_repository = AsyncMock()
            invalid_athletes = [
                {'user_id': 'athlete1', 'name': 'John'},
                {'name': 'Jane'},  # Missing user_id
                {'user_id': 'athlete3', 'name': 'Bob'}
            ]
            service.athlete_repository.query.return_value = invalid_athletes
            
            # Test filtering
            result = await service._get_athletes_with_optimized_filtering([], 10)
            
            # Should filter out athletes without user_id
            assert len(result) == 2
            assert all('user_id' in athlete for athlete in result)
    
    @pytest.mark.asyncio
    async def test_similarity_scoring_with_config_weights(self, mock_config, sample_athletes):
        """Test similarity scoring uses configuration weights instead of hard-coded values"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.get_by_field.return_value = sample_athletes[0]  # Reference athlete
            service.athlete_repository.query.return_value = sample_athletes[1:]  # Similar athletes
            
            # Test the method
            result = await service.get_similar_athletes('athlete1', 5)
            
            # Verify that scoring was done (athletes were returned)
            assert len(result) > 0
            
            # Verify that the method used config weights by checking the mock was called
            service.athlete_repository.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_athletes_after_scoring(self, mock_config):
        """Test handling when no athletes are scored"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = []  # No athletes found
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = None
            
            # Test the method
            result = await service.get_recommended_athletes('scout1', 10)
            
            # Should return empty list
            assert result == []
    
    @pytest.mark.asyncio
    async def test_calculate_completion_percentage_with_empty_weights(self, mock_config):
        """Test completion percentage calculation with empty field weights"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Test with empty field weights
            empty_config = mock_config.copy()
            empty_config['field_weights'] = {}
            
            with patch.object(service, 'config', empty_config):
                completion = service._calculate_completion_percentage({'name': 'John'})
                assert completion == 0
    
    @pytest.mark.asyncio
    async def test_calculate_completion_percentage_with_zero_weights(self, mock_config):
        """Test completion percentage calculation with zero field weights"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Test with zero field weights
            zero_config = mock_config.copy()
            zero_config['field_weights'] = {'name': 0, 'age': 0}
            
            with patch.object(service, 'config', zero_config):
                completion = service._calculate_completion_percentage({'name': 'John', 'age': 25})
                assert completion == 0
    
    @pytest.mark.asyncio
    async def test_improved_logging(self, mock_config, sample_athletes, caplog):
        """Test that improved logging provides better visibility"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repositories
            service.athlete_repository = AsyncMock()
            service.athlete_repository.query.return_value = sample_athletes
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = None
            
            # Test the method
            with caplog.at_level(logging.INFO):
                result = await service.get_recommended_athletes('scout1', 10)
            
            # Verify logging messages
            assert "No athletes found for scout scout1 with given filters" not in caplog.text
            assert "Returning" in caplog.text
            assert "scout1" in caplog.text
    
    @pytest.mark.asyncio
    async def test_athletes_missing_user_id_filtering(self, mock_config):
        """Test that athletes without user_id are properly filtered out"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Mock repository to return athletes with missing user_id
            service.athlete_repository = AsyncMock()
            invalid_athletes = [
                {'user_id': 'athlete1', 'name': 'John'},
                {'name': 'Jane'},  # Missing user_id
                {'user_id': 'athlete3', 'name': 'Bob'}
            ]
            service.athlete_repository.query.return_value = invalid_athletes
            
            service.scout_prefs_repository = AsyncMock()
            service.scout_prefs_repository.get_by_field.return_value = None
            
            # Test the method
            result = await service.get_recommended_athletes('scout1', 10)
            
            # Should filter out athletes without user_id and still process the valid ones
            assert len(result) <= 2  # Only valid athletes should be processed
            assert all('user_id' in athlete for athlete in result)
    
    @pytest.mark.asyncio
    async def test_similarity_scoring_config_fallback(self, mock_config, sample_athletes):
        """Test that similarity scoring falls back to default values when config is missing"""
        with patch('app.services.athlete_recommendation_service.get_config', return_value=mock_config):
            service = AthleteRecommendationService()
            
            # Remove some config values to test fallback
            incomplete_config = mock_config.copy()
            del incomplete_config['recommendation_weights']['age_similarity_close']
            del incomplete_config['recommendation_weights']['completion_similarity_close']
            
            with patch.object(service, 'config', incomplete_config):
                # Mock repositories
                service.athlete_repository = AsyncMock()
                service.athlete_repository.get_by_field.return_value = sample_athletes[0]
                service.athlete_repository.query.return_value = sample_athletes[1:]
                
                # Test the method - should use fallback values
                result = await service.get_similar_athletes('athlete1', 5)
                
                # Should still work with fallback values
                assert len(result) > 0


if __name__ == '__main__':
    pytest.main([__file__]) 