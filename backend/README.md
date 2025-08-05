# Athletes Networking API

A comprehensive FastAPI-based REST API for an athletes networking platform that connects athletes with scouts and opportunities. The platform features AI-powered media analysis, real-time messaging, and advanced search capabilities.

## 🚀 Features

### Core Functionality
- **User Authentication & Authorization**: Firebase-based authentication with role-based access control
- **Athlete Profiles**: Comprehensive athlete profiles with stats, achievements, and media
- **Scout Profiles**: Verified scout profiles with credentials and experience
- **Opportunities**: Job/opportunity posting and application system
- **Media Management**: AI-powered video/image analysis and recommendations
- **Messaging System**: Real-time conversations between athletes and scouts
- **Notifications**: Comprehensive notification system with preferences
- **Admin Panel**: Full administrative capabilities for platform management

### Technical Features
- **FastAPI Framework**: High-performance async API with automatic documentation
- **Firebase Integration**: Firestore database and Firebase Authentication
- **AI-Powered Analysis**: Media analysis with ratings, summaries, and recommendations
- **Rate Limiting**: Comprehensive rate limiting for API protection
- **Comprehensive Testing**: Unit, integration, and API tests with 80%+ coverage
- **Security**: Input validation, authentication, authorization, and error handling
- **Scalability**: Efficient database queries, caching, and background tasks

## 🏗️ Architecture

### Project Structure
```
backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── auth.py          # Authentication endpoints
│   │   │   ├── users.py         # User management endpoints
│   │   │   ├── athletes.py      # Athlete-specific endpoints
│   │   │   ├── scouts.py        # Scout-specific endpoints
│   │   │   ├── media.py         # Media management endpoints
│   │   │   ├── opportunities.py # Opportunity management endpoints
│   │   │   ├── conversations.py # Messaging endpoints
│   │   │   ├── notifications.py # Notification endpoints
│   │   │   └── admin.py         # Admin endpoints
│   │   ├── dependencies.py      # Authentication dependencies
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── middleware.py        # Rate limiting, logging, error handling
│   ├── models/                  # Pydantic models for data validation
│   ├── services/                # Business logic layer
│   └── firebaseConfig/          # Firebase configuration
├── test/                        # Comprehensive test suite
├── main.py                      # FastAPI application entry point
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

### Technology Stack
- **Framework**: FastAPI 0.104.1
- **Database**: Firebase Firestore
- **Authentication**: Firebase Authentication
- **Testing**: pytest with async support
- **Rate Limiting**: slowapi
- **Validation**: Pydantic
- **Documentation**: Automatic OpenAPI/Swagger docs

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Firebase project with Firestore and Authentication enabled
- Firebase service account key

### 1. Clone the Repository
```bash
git clone <repository-url>
cd backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the backend directory:
```env
# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com

# Application Settings
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# AI Service (for media analysis)
AI_SERVICE_ENABLED=true
AI_ANALYSIS_RETRY_ATTEMPTS=3
AI_ANALYSIS_RETRY_DELAY=5

# Email Configuration (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 5. Firebase Setup
1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Enable Firestore Database
3. Enable Authentication with Email/Password
4. Create a service account and download the JSON key
5. Update the `.env` file with your Firebase credentials

### 6. Run the Application
```bash
# Development mode
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Tests with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest -m unit

# API tests only
pytest -m api

# Authentication tests only
pytest -m auth

# Integration tests only
pytest -m integration
```

### Test Coverage Report
After running tests with coverage, view the HTML report:
```bash
open htmlcov/index.html  # On macOS
# or
start htmlcov/index.html  # On Windows
```

## 📚 API Documentation

Once the application is running, you can access:

- **Interactive API Docs (Swagger UI)**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🔐 Authentication

The API uses Firebase Authentication with JWT tokens. All protected endpoints require a valid Bearer token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### User Roles
- **athlete**: Can create athlete profiles, upload media, apply for opportunities
- **scout**: Can create scout profiles, post opportunities, review applications
- **admin**: Full administrative access to all features

## 🚀 API Endpoints

### Authentication (`/api/v1/auth`)
- `POST /register` - User registration
- `POST /login` - User login
- `POST /refresh` - Refresh access token
- `POST /logout` - User logout
- `POST /verify-email` - Email verification
- `POST /forgot-password` - Password reset request
- `POST /reset-password` - Password reset

### Users (`/api/v1/users`)
- `GET /profile` - Get current user profile
- `PUT /profile` - Update user profile
- `DELETE /profile` - Delete user profile
- `GET /settings` - Get user settings
- `PUT /settings` - Update user settings

### Athletes (`/api/v1/athletes`)
- `POST /profile` - Create athlete profile
- `GET /profile` - Get athlete profile
- `PUT /profile` - Update athlete profile
- `DELETE /profile` - Delete athlete profile
- `GET /search` - Search athletes
- `GET /stats` - Get athlete statistics
- `GET /recommendations` - Get personalized recommendations

### Scouts (`/api/v1/scouts`)
- `POST /profile` - Create scout profile
- `GET /profile` - Get scout profile
- `PUT /profile` - Update scout profile
- `DELETE /profile` - Delete scout profile
- `GET /search` - Search scouts
- `GET /stats` - Get scout statistics
- `POST /verification` - Submit verification documents

### Media (`/api/v1/media`)
- `POST /upload` - Upload media file
- `GET /` - Get user media
- `GET /{media_id}` - Get specific media
- `PUT /{media_id}` - Update media
- `DELETE /{media_id}` - Delete media
- `GET /search` - Search media
- `GET /{media_id}/analysis` - Get AI analysis
- `POST /{media_id}/analyze` - Trigger AI analysis
- `GET /recommended` - Get recommended media
- `GET /trending` - Get trending media

### Opportunities (`/api/v1/opportunities`)
- `POST /` - Create opportunity
- `GET /` - Search opportunities
- `GET /{opportunity_id}` - Get specific opportunity
- `PUT /{opportunity_id}` - Update opportunity
- `DELETE /{opportunity_id}` - Delete opportunity
- `POST /{opportunity_id}/apply` - Apply for opportunity
- `GET /{opportunity_id}/applications` - Get applications
- `PUT /{opportunity_id}/applications/{application_id}` - Update application status

### Conversations (`/api/v1/conversations`)
- `POST /` - Create conversation
- `GET /` - Get user conversations
- `GET /{conversation_id}` - Get specific conversation
- `DELETE /{conversation_id}` - Delete conversation
- `POST /{conversation_id}/messages` - Send message
- `GET /{conversation_id}/messages` - Get messages
- `PUT /{conversation_id}/messages/{message_id}` - Edit message
- `DELETE /{conversation_id}/messages/{message_id}` - Delete message

### Notifications (`/api/v1/notifications`)
- `GET /` - Get user notifications
- `GET /{notification_id}` - Get specific notification
- `POST /{notification_id}/read` - Mark as read
- `POST /mark-all-read` - Mark all as read
- `DELETE /{notification_id}` - Delete notification
- `GET /unread/count` - Get unread count
- `GET /settings` - Get notification settings
- `PUT /settings` - Update notification settings

### Admin (`/api/v1/admin`)
- `GET /users` - Search users
- `GET /users/{user_id}` - Get user details
- `PUT /users/{user_id}/status` - Update user status
- `DELETE /users/{user_id}` - Delete user
- `GET /verifications` - Get pending verifications
- `PUT /verifications/{verification_id}/status` - Update verification status
- `GET /reports` - Get user reports
- `PUT /reports/{report_id}/status` - Update report status
- `GET /stats/overview` - Get admin statistics

## 🔧 Configuration

### Rate Limiting
Configure rate limiting in the `.env` file:
```env
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

### AI Analysis
Configure AI analysis settings:
```env
AI_SERVICE_ENABLED=true
AI_ANALYSIS_RETRY_ATTEMPTS=3
AI_ANALYSIS_RETRY_DELAY=5
```

### Email Configuration
For email functionality (verification, password reset):
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## 🚀 Deployment

### Docker Deployment
1. Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

2. Build and run:
```bash
docker build -t athletes-api .
docker run -p 8000:8000 athletes-api
```

### Production Considerations
- Use environment variables for all sensitive configuration
- Enable HTTPS in production
- Set up proper logging and monitoring
- Configure Firebase security rules
- Set up database backups
- Use a production-grade WSGI server like Gunicorn

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the API documentation at `/docs`
- Review the test examples for usage patterns

## 🔄 Version History

- **v1.0.0**: Initial release with full API implementation
  - Complete authentication system
  - Athlete and scout profile management
  - Media upload and AI analysis
  - Opportunity posting and applications
  - Real-time messaging system
  - Comprehensive notification system
  - Admin panel with full capabilities
  - Complete test suite with 80%+ coverage 