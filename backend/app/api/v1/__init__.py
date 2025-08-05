from fastapi import APIRouter
from .auth import router as auth_router
from .users import router as users_router
from .athletes import router as athletes_router
from .scouts import router as scouts_router
from .media import router as media_router
from .opportunities import router as opportunities_router
from .conversations import router as conversations_router
from .notifications import router as notifications_router
from .admin import router as admin_router

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all route modules
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(athletes_router, prefix="/athletes", tags=["Athletes"])
router.include_router(scouts_router, prefix="/scouts", tags=["Scouts"])
router.include_router(media_router, prefix="/media", tags=["Media"])
router.include_router(opportunities_router, prefix="/opportunities", tags=["Opportunities"])
router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])
router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
router.include_router(admin_router, prefix="/admin", tags=["Admin"]) 