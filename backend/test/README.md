# Test Suite Documentation

This directory contains the comprehensive test suite for the Athletes Networking API. The tests are organized into separate files for better maintainability and focused testing.

## 📁 Test Structure

```
test/
├── conftest.py                     # Shared fixtures and test configuration
├── pytest.ini                     # Pytest configuration
├── run_tests.py                   # Test runner script
├── README.md                      # This file
├── test_services.py               # Legacy file (redirects to individual files)
├── test_api.py                    # Legacy file (redirects to individual files)
├── services/                      # Service layer tests
│   ├── __init__.py
│   ├── test_database_service.py   # DatabaseService tests
│   ├── test_auth_service.py       # AuthService tests
│   ├── test_user_service.py       # UserService tests
│   ├── test_athlete_service.py    # AthleteService tests
│   ├── test_scout_service.py      # ScoutService tests
│   ├── test_media_service.py              # MediaService tests (refactored)
│   ├── test_opportunity_service.py # OpportunityService tests
│   ├── test_conversation_service.py # ConversationService tests
│   ├── test_notification_service.py # NotificationService tests
│   └── test_ai_service.py         # AIService tests
└── api/                          # API endpoint tests
    ├── __init__.py
    ├── test_auth_api.py          # Authentication API tests
    ├── test_users_api.py         # Users API tests
    ├── test_athletes_api.py      # Athletes API tests
    ├── test_scouts_api.py        # Scouts API tests (to be created)
    ├── test_media_api.py         # Media API tests
    ├── test_opportunities_api.py # Opportunities API tests
    ├── test_conversations_api.py # Conversations API tests (to be created)
    ├── test_notifications_api.py # Notifications API tests (to be created)
    ├── test_admin_api.py         # Admin API tests
    └── test_error_handling.py   # General error handling tests
```

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test category
pytest test/services/                    # All service tests
pytest test/api/                        # All API tests
pytest test/services/test_auth_service.py # Specific service tests
pytest test/api/test_auth_api.py        # Specific API tests
```

### Using the Test Runner Script

The `run_tests.py` script provides convenient commands for different test scenarios:

```bash
# Run all tests
python test/run_tests.py all

# Run only service tests
python test/run_tests.py services

# Run only API tests
python test/run_tests.py api

# Run tests by functionality
python test/run_tests.py auth          # Authentication tests
python test/run_tests.py athletes     # Athlete-related tests
python test/run_tests.py scouts       # Scout-related tests
python test/run_tests.py media        # Media-related tests
python test/run_tests.py opportunities # Opportunity-related tests
python test/run_tests.py admin        # Admin-related tests

# Run by speed
python test/run_tests.py fast         # Fast tests only
python test/run_tests.py slow         # Slow tests only

# Run with options
python test/run_tests.py all --verbose --parallel
python test/run_tests.py services --no-cov
```

### Test Categories and Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.api` - API tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.service` - Service layer tests
- `@pytest.mark.athlete` - Athlete functionality tests
- `@pytest.mark.scout` - Scout functionality tests
- `@pytest.mark.media` - Media functionality tests
- `@pytest.mark.opportunity` - Opportunity functionality tests
- `@pytest.mark.admin` - Admin functionality tests
- `@pytest.mark.slow` - Slow running tests

### Running Tests by Markers

```bash
# Run only unit tests
pytest -m unit

# Run only API tests
pytest -m api

# Run only fast tests (exclude slow ones)
pytest -m "not slow"

# Run authentication-related tests
pytest -m auth

# Run athlete functionality tests
pytest -m athlete
```

## 🧪 Test Types

### Service Layer Tests (`test/services/`)

These tests focus on testing the business logic in isolation:

- **Database Service**: CRUD operations, queries, transactions
- **Auth Service**: User authentication, token management
- **User Service**: User profile management, settings
- **Athlete Service**: Athlete profiles, stats, recommendations
- **Scout Service**: Scout profiles, verification
- **Media Service**: File upload, AI analysis triggers
- **Opportunity Service**: Opportunity CRUD, applications
- **Conversation Service**: Messaging system
- **Notification Service**: Notification management
- **AI Service**: Media analysis, recommendations

### API Layer Tests (`test/api/`)

These tests focus on HTTP endpoints and request/response handling:

- **Auth API**: Registration, login, password management
- **Users API**: Profile management, settings, blocking
- **Athletes API**: Athlete-specific endpoints
- **Scouts API**: Scout-specific endpoints
- **Media API**: Media upload, analysis, search
- **Opportunities API**: Opportunity management, applications
- **Conversations API**: Messaging endpoints
- **Notifications API**: Notification endpoints
- **Admin API**: Administrative functions
- **Error Handling**: General error scenarios

## 🔧 Test Configuration

### Fixtures (`conftest.py`)

Common fixtures are defined in `conftest.py`:

- `client` - FastAPI test client
- `mock_firestore` - Mocked Firestore client
- `mock_auth` - Mocked Firebase Auth client
- `mock_current_user` - Mock user data
- `mock_athlete_user` - Mock athlete user
- `mock_scout_user` - Mock scout user
- `mock_admin_user` - Mock admin user
- Service fixtures with mocked dependencies

### Configuration (`pytest.ini`)

- Coverage reporting (HTML and terminal)
- Test discovery patterns
- Async test support
- Warning filters
- Custom markers

## 📊 Coverage Reports

After running tests with coverage, view the reports:

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# Open the report
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
```

## 🎯 Best Practices

### Writing Tests

1. **Descriptive Names**: Use clear, descriptive test names
2. **Arrange-Act-Assert**: Follow the AAA pattern
3. **Mock External Dependencies**: Use mocks for database, external APIs
4. **Test Edge Cases**: Include error scenarios and edge cases
5. **Keep Tests Independent**: Each test should be isolated

### Example Test Structure

```python
@pytest.mark.asyncio
@pytest.mark.service
@pytest.mark.athlete
async def test_create_athlete_profile_success(self, mock_athlete_service):
    """Test creating athlete profile successfully"""
    # Arrange
    profile_data = {
        "first_name": "John",
        "last_name": "Doe",
        "sport": "football"
    }
    
    # Act
    result = await mock_athlete_service.create_profile("user123", profile_data)
    
    # Assert
    assert result is not None
    assert result["sport"] == "football"
    mock_athlete_service.database_service.create_document.assert_called_once()
```

## 🔍 Debugging Tests

### Running Individual Tests

```bash
# Run a specific test method
pytest test/services/test_auth_service.py::TestAuthService::test_login_user_success

# Run with verbose output
pytest -v test/services/test_auth_service.py

# Run with debugging
pytest -s test/services/test_auth_service.py  # Show print statements
pytest --pdb test/services/test_auth_service.py  # Drop into debugger on failure
```

### Common Issues

1. **Import Errors**: Make sure the `backend` directory is in Python path
2. **Async Issues**: Use `@pytest.mark.asyncio` for async tests
3. **Mock Issues**: Ensure mocks are properly configured in fixtures
4. **Firebase Errors**: Check that Firebase config is properly mocked

## 📈 Continuous Integration

The test suite is designed to work with CI/CD pipelines:

```yaml
# Example GitHub Actions configuration
- name: Run Tests
  run: |
    cd backend
    pytest --cov=app --cov-report=xml --cov-fail-under=80
```

## 🔮 Future Enhancements

Planned improvements to the test suite:

1. **Performance Tests**: Load testing for API endpoints
2. **End-to-End Tests**: Full workflow testing
3. **Contract Tests**: API contract validation
4. **Security Tests**: Authentication and authorization testing
5. **Database Integration Tests**: Real database testing

---

For questions or issues with the test suite, please refer to the main project documentation or create an issue in the repository. 