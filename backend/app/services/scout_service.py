from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timezone

from ..models.scout import ScoutProfile, ScoutProfileCreate, ScoutProfileUpdate, ScoutSearchFilters, ScoutAnalytics, ScoutVerificationRequest
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError

logger = logging.getLogger(__name__)


class ScoutService:
    """Scout service for managing scout profiles and related operations"""
    
    def __init__(self):
        self.scout_service = DatabaseService("scout_profiles")
        self.user_service = DatabaseService("users")
        self.opportunity_service = DatabaseService("opportunities")
        self.application_service = DatabaseService("applications")
        # Analytics tracking collections
        self.scout_activity_service = DatabaseService("scout_activity")
        self.conversation_service = DatabaseService("conversations")
        self.message_service = DatabaseService("messages")
    
    async def create_scout_profile(self, user_id: str, profile_data: ScoutProfileCreate) -> Dict[str, Any]:
        """Create scout profile"""
        try:
            # Input validation
            if not user_id:
                raise ValidationError("User ID is required for scout profile creation")
            if not profile_data.first_name or not profile_data.last_name or not profile_data.organization or not profile_data.title:
                raise ValidationError("Missing required fields for scout profile creation")

            # Check if profile already exists
            existing_profile = await self.scout_service.get_by_field("user_id", user_id)
            if existing_profile:
                raise ValidationError("Scout profile already exists for this user")
            
            # Create scout profile
            profile_doc = {
                "user_id": user_id,
                "first_name": profile_data.first_name,
                "last_name": profile_data.last_name,
                "organization": profile_data.organization,
                "title": profile_data.title,
                "verification_status": "pending",
                "focus_areas": profile_data.focus_areas or []
            }
            
            try:
                profile_id = await self.scout_service.create(profile_doc)
            except Exception as e:
                logger.error(f"Database error creating scout profile: {e}")
                raise DatabaseError(f"Failed to create scout profile: {str(e)}")
            
            return await self.get_scout_profile(user_id)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating scout profile for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create scout profile: {str(e)}")
    
    async def get_scout_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get scout profile by user ID"""
        try:
            if not user_id:
                raise ValidationError("User ID is required to fetch scout profile")
            profile_doc = await self.scout_service.get_by_field("user_id", user_id)
            if not profile_doc:
                raise ResourceNotFoundError("Scout profile", user_id)
            return profile_doc
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting scout profile for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get scout profile: {str(e)}")
    
    async def update_scout_profile(self, user_id: str, profile_data: ScoutProfileUpdate) -> Dict[str, Any]:
        """Update scout profile"""
        try:
            if not user_id:
                raise ValidationError("User ID is required for scout profile update")
            update_data = {}
            
            if profile_data.first_name is not None:
                update_data["first_name"] = profile_data.first_name
            if profile_data.last_name is not None:
                update_data["last_name"] = profile_data.last_name
            if profile_data.organization is not None:
                update_data["organization"] = profile_data.organization
            if profile_data.title is not None:
                update_data["title"] = profile_data.title
            if profile_data.focus_areas is not None:
                update_data["focus_areas"] = profile_data.focus_areas
            
            if not update_data:
                raise ValidationError("No valid fields provided for update")
            # Find the profile document ID
            profile_doc = await self.scout_service.get_by_field("user_id", user_id)
            if not profile_doc:
                raise ResourceNotFoundError("Scout profile", user_id)
            try:
                await self.scout_service.update(profile_doc["id"], update_data)
            except Exception as e:
                logger.error(f"Database error updating scout profile: {e}")
                raise DatabaseError(f"Failed to update scout profile: {str(e)}")
            return await self.get_scout_profile(user_id)
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error updating scout profile for user {user_id}: {e}")
            raise DatabaseError(f"Failed to update scout profile: {str(e)}")
    
    async def search_scouts(self, filters: ScoutSearchFilters) -> PaginatedResponse:
        """Search scouts with filters"""
        try:
            firestore_filters = []
            
            if filters.organization:
                firestore_filters.append(FieldFilter("organization", "==", filters.organization))
            
            if filters.location:
                firestore_filters.append(FieldFilter("location", "==", filters.location))
            
            if filters.sport:
                firestore_filters.append(FieldFilter("focus_areas", "array_contains", filters.sport))
            
            try:
                scouts = await self.scout_service.query(firestore_filters, filters.limit, filters.offset)
                total_count = await self.scout_service.count(firestore_filters)
            except Exception as e:
                logger.error(f"Database error searching scouts: {e}")
                raise DatabaseError(f"Failed to search scouts: {str(e)}")
            
            return PaginatedResponse(
                count=total_count,
                results=scouts,
                next=f"?limit={filters.limit}&offset={filters.offset + filters.limit}" if filters.offset + filters.limit < total_count else None,
                previous=f"?limit={filters.limit}&offset={max(0, filters.offset - filters.limit)}" if filters.offset > 0 else None
            )
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error searching scouts: {e}")
            raise DatabaseError(f"Failed to search scouts: {str(e)}")
    
    async def get_scout_opportunities(self, scout_id: str, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get opportunities created by scout"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required to fetch opportunities")
            filters = [FieldFilter("scout_id", "==", scout_id)]
            
            if status:
                filters.append(FieldFilter("is_active", "==", status == "active"))
            try:
                opportunities = await self.opportunity_service.query(filters, limit, offset)
            except Exception as e:
                logger.error(f"Database error getting scout opportunities: {e}")
                raise DatabaseError(f"Failed to get scout opportunities: {str(e)}")
            return opportunities
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting scout opportunities for {scout_id}: {e}")
            raise DatabaseError(f"Failed to get scout opportunities: {str(e)}")
    
    async def track_athlete_view(self, scout_id: str, athlete_id: str) -> bool:
        """Track when a scout views an athlete profile"""
        try:
            if not scout_id or not athlete_id:
                raise ValidationError("Scout ID and Athlete ID are required for tracking")
            
            # Create activity record
            activity_data = {
                "scout_id": scout_id,
                "athlete_id": athlete_id,
                "activity_type": "athlete_view",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "view_source": "profile_page",
                    "session_id": None  # Could be added for session tracking
                }
            }
            
            try:
                await self.scout_activity_service.create(activity_data)
                logger.info(f"Tracked athlete view: scout {scout_id} viewed athlete {athlete_id}")
                return True
            except Exception as e:
                logger.error(f"Database error tracking athlete view: {e}")
                raise DatabaseError(f"Failed to track athlete view: {str(e)}")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error tracking athlete view for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to track athlete view: {str(e)}")
    
    async def track_search_performed(self, scout_id: str, search_type: str, query: str, filters: Dict[str, Any]) -> bool:
        """Track when a scout performs a search"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required for tracking search")
            
            # Create activity record
            activity_data = {
                "scout_id": scout_id,
                "activity_type": "search_performed",
                "search_type": search_type,
                "query": query,
                "filters": filters,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "search_source": "scout_dashboard",
                    "results_count": 0  # Could be updated after search results are known
                }
            }
            
            try:
                await self.scout_activity_service.create(activity_data)
                logger.info(f"Tracked search: scout {scout_id} performed {search_type} search")
                return True
            except Exception as e:
                logger.error(f"Database error tracking search: {e}")
                raise DatabaseError(f"Failed to track search: {str(e)}")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error tracking search for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to track search: {str(e)}")
    
    async def track_message_sent(self, scout_id: str, conversation_id: str, message_id: str, recipient_id: str) -> bool:
        """Track when a scout sends a message"""
        try:
            if not scout_id or not conversation_id or not message_id or not recipient_id:
                raise ValidationError("All parameters are required for tracking message")
            
            # Create activity record
            activity_data = {
                "scout_id": scout_id,
                "activity_type": "message_sent",
                "conversation_id": conversation_id,
                "message_id": message_id,
                "recipient_id": recipient_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "message_type": "text",  # Could be enhanced for different message types
                    "conversation_type": "direct"
                }
            }
            
            try:
                await self.scout_activity_service.create(activity_data)
                logger.info(f"Tracked message: scout {scout_id} sent message {message_id}")
                return True
            except Exception as e:
                logger.error(f"Database error tracking message: {e}")
                raise DatabaseError(f"Failed to track message: {str(e)}")
                
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error tracking message for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to track message: {str(e)}")
    
    async def get_scout_analytics(self, scout_id: str) -> ScoutAnalytics:
        """Get scout analytics with real tracking data"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required for analytics")
            
            # Count opportunities created
            opportunity_filters = [FieldFilter("scout_id", "==", scout_id)]
            opportunities_created = await self.opportunity_service.count(opportunity_filters)
            
            # Count applications received
            application_filters = [FieldFilter("scout_id", "==", scout_id)]
            applications_received = await self.application_service.count(application_filters)
            
            # Count athletes viewed (from activity tracking)
            athlete_view_filters = [
                FieldFilter("scout_id", "==", scout_id),
                FieldFilter("activity_type", "==", "athlete_view")
            ]
            athletes_viewed = await self.scout_activity_service.count(athlete_view_filters)
            
            # Count searches performed (from activity tracking)
            search_filters = [
                FieldFilter("scout_id", "==", scout_id),
                FieldFilter("activity_type", "==", "search_performed")
            ]
            searches_performed = await self.scout_activity_service.count(search_filters)
            
            # Count messages sent (from activity tracking)
            message_filters = [
                FieldFilter("scout_id", "==", scout_id),
                FieldFilter("activity_type", "==", "message_sent")
            ]
            messages_sent = await self.scout_activity_service.count(message_filters)
            
            return ScoutAnalytics(
                athletes_viewed=athletes_viewed,
                searches_performed=searches_performed,
                opportunities_created=opportunities_created,
                applications_received=applications_received,
                messages_sent=messages_sent
            )
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting scout analytics for {scout_id}: {e}")
            raise DatabaseError(f"Failed to get scout analytics: {str(e)}")
    
    async def verify_scout(self, scout_id: str, verification_data: ScoutVerificationRequest) -> Dict[str, Any]:
        """Verify or reject scout profile"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required for verification")
            profile_doc = await self.scout_service.get_by_field("user_id", scout_id)
            if not profile_doc:
                raise ResourceNotFoundError("Scout profile", scout_id)
            update_data = {
                "verification_status": verification_data.status
            }
            if verification_data.notes:
                update_data["verification_notes"] = verification_data.notes
                update_data["verification_date"] = datetime.now(timezone.utc)
            try:
                await self.scout_service.update(profile_doc["id"], update_data)
            except Exception as e:
                logger.error(f"Database error verifying scout: {e}")
                raise DatabaseError(f"Failed to verify scout: {str(e)}")
            return await self.get_scout_profile(scout_id)
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error verifying scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to verify scout: {str(e)}")
    
    async def get_scout_by_id(self, scout_id: str) -> Optional[Dict[str, Any]]:
        """Get scout profile by scout ID (user ID)"""
        try:
            return await self.get_scout_profile(scout_id)
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting scout by ID {scout_id}: {e}")
            raise DatabaseError(f"Failed to get scout by ID: {str(e)}")
    
    async def delete_scout_profile(self, user_id: str) -> bool:
        """Delete scout profile"""
        try:
            if not user_id:
                raise ValidationError("User ID is required to delete scout profile")
            profile_doc = await self.scout_service.get_by_field("user_id", user_id)
            if not profile_doc:
                raise ResourceNotFoundError("Scout profile", user_id)
            try:
                await self.scout_service.delete(profile_doc["id"])
            except Exception as e:
                logger.error(f"Database error deleting scout profile: {e}")
                raise DatabaseError(f"Failed to delete scout profile: {str(e)}")
            return True
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error deleting scout profile for user {user_id}: {e}")
            raise DatabaseError(f"Failed to delete scout profile: {str(e)}")
    
    async def get_pending_verifications(self, limit: int = 100, offset: int = 0) -> PaginatedResponse:
        """Get scouts pending verification"""
        try:
            filters = [FieldFilter("verification_status", "==", "pending")]
            try:
                scouts = await self.scout_service.query(filters, limit, offset)
                total_count = await self.scout_service.count(filters)
            except Exception as e:
                logger.error(f"Database error getting pending verifications: {e}")
                raise DatabaseError(f"Failed to get pending verifications: {str(e)}")
            return PaginatedResponse(
                count=total_count,
                results=scouts,
                next=f"?limit={limit}&offset={offset + limit}" if offset + limit < total_count else None,
                previous=f"?limit={limit}&offset={max(0, offset - limit)}" if offset > 0 else None
            )
        except Exception as e:
            logger.error(f"Error getting pending verifications: {e}")
            raise DatabaseError(f"Failed to get pending verifications: {str(e)}")
    
    async def get_scout_activity_summary(self, scout_id: str, days: int = 30) -> Dict[str, Any]:
        """Get detailed activity summary for a scout"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required for activity summary")
            
            # Calculate date threshold
            from datetime import timedelta
            threshold_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            # Get recent activities
            activity_filters = [
                FieldFilter("scout_id", "==", scout_id),
                FieldFilter("timestamp", ">=", threshold_date)
            ]
            
            activities = await self.scout_activity_service.query(activity_filters, limit=1000)
            
            # Group activities by type
            activity_summary = {
                "athlete_views": [],
                "searches": [],
                "messages": [],
                "total_activities": len(activities)
            }
            
            for activity in activities:
                activity_type = activity.get("activity_type")
                if activity_type == "athlete_view":
                    activity_summary["athlete_views"].append(activity)
                elif activity_type == "search_performed":
                    activity_summary["searches"].append(activity)
                elif activity_type == "message_sent":
                    activity_summary["messages"].append(activity)
            
            # Add counts
            activity_summary["athlete_views_count"] = len(activity_summary["athlete_views"])
            activity_summary["searches_count"] = len(activity_summary["searches"])
            activity_summary["messages_count"] = len(activity_summary["messages"])
            
            return activity_summary
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting scout activity summary for {scout_id}: {e}")
            raise DatabaseError(f"Failed to get scout activity summary: {str(e)}") 