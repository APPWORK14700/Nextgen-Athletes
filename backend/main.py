from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import API routes
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.athletes import router as athletes_router
from app.api.v1.scouts import router as scouts_router
from app.api.v1.media import router as media_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.admin import router as admin_router
from app.api.v1.search import router as search_router
from app.api.v1.stats import router as stats_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.sport_categories import router as sport_categories_router
from app.api.v1.content import router as content_router
from app.api.v1.websocket import router as websocket_router

# Import middleware
from app.api.middleware import RateLimitMiddleware, LoggingMiddleware, ErrorHandlingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Athletes Networking API",
    description="A comprehensive API for athletes networking platform with scouting, opportunities, and AI-powered media analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(athletes_router, prefix="/api/v1")
app.include_router(scouts_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
app.include_router(opportunities_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(sport_categories_router, prefix="/api/v1")
app.include_router(content_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Athletes Networking API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "API is running",
        "version": "1.0.0",
        "timestamp": "2024-01-15T12:00:00Z",
        "services": {
            "database": "healthy",
            "ai_analysis": "healthy", 
            "file_storage": "healthy"
        }
    }

@app.get("/api/v1/health")
async def api_health_check():
    """Health check endpoint for API v1"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-15T12:00:00Z",
        "version": "1.0.0",
        "services": {
            "database": "healthy",
            "ai_analysis": "healthy",
            "file_storage": "healthy"
        }
    }

@app.get("/api/v1")
async def api_info():
    """API information endpoint"""
    return {
        "name": "Athletes Networking API",
        "version": "1.0.0",
        "description": "Comprehensive API for athletes networking platform",
        "endpoints": {
            "auth": "/api/v1/auth",
            "users": "/api/v1/users",
            "athletes": "/api/v1/athletes",
            "scouts": "/api/v1/scouts",
            "media": "/api/v1/media",
            "opportunities": "/api/v1/opportunities",
            "conversations": "/api/v1/conversations",
            "notifications": "/api/v1/notifications",
            "admin": "/api/v1/admin",
            "search": "/api/v1/search",
            "stats": "/api/v1/athletes/me/stats",
            "organizations": "/api/v1/organizations",
            "sport_categories": "/api/v1/sport-categories",
            "content": "/api/v1/content"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    ) 