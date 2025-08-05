from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, date, timezone

from ..models.opportunity import Opportunity, OpportunityCreate, OpportunityUpdate, OpportunitySearchFilters, OpportunityToggleRequest
from ..models.application import Application, ApplicationCreate, ApplicationStatusUpdate
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter
from app.api.exceptions import ValidationError, ResourceNotFoundError, DatabaseError

logger = logging.getLogger(__name__)


class OpportunityService:
    """Opportunity service for managing opportunities and applications"""
    
    def __init__(self):
        self.opportunity_service = DatabaseService("opportunities")
        self.application_service = DatabaseService("applications")
    
    async def create_opportunity(self, scout_id: str, opportunity_data: OpportunityCreate) -> Dict[str, Any]:
        """Create new opportunity"""
        try:
            # Input validation
            if not scout_id:
                raise ValidationError("Scout ID is required for opportunity creation")
            
            # Validate date range
            if opportunity_data.end_date and opportunity_data.end_date < opportunity_data.start_date:
                raise ValidationError("End date cannot be before start date")
            
            # Create opportunity document
            opportunity_doc = {
                "scout_id": scout_id,
                "title": opportunity_data.title,
                "description": opportunity_data.description,
                "type": opportunity_data.type,
                "sport_category_id": opportunity_data.sport_category_id,
                "location": opportunity_data.location,
                "start_date": opportunity_data.start_date.isoformat(),
                "end_date": opportunity_data.end_date.isoformat() if opportunity_data.end_date else None,
                "requirements": opportunity_data.requirements,
                "compensation": opportunity_data.compensation,
                "is_active": True,
                "moderation_status": "pending"
            }
            
            try:
                opportunity_id = await self.opportunity_service.create(opportunity_doc)
            except Exception as e:
                logger.error(f"Database error creating opportunity: {e}")
                raise DatabaseError(f"Failed to create opportunity: {str(e)}")
            
            return await self.get_opportunity_by_id(opportunity_id)
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error creating opportunity for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to create opportunity: {str(e)}")
    
    async def get_opportunity_by_id(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        """Get opportunity by ID"""
        try:
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required")
            
            try:
                opportunity_doc = await self.opportunity_service.get_by_id(opportunity_id)
            except Exception as e:
                logger.error(f"Database error getting opportunity: {e}")
                raise DatabaseError(f"Failed to get opportunity: {str(e)}")
            
            if not opportunity_doc:
                raise ResourceNotFoundError("Opportunity", opportunity_id)
            
            # Convert date strings back to date objects
            if "start_date" in opportunity_doc:
                opportunity_doc["start_date"] = datetime.fromisoformat(opportunity_doc["start_date"]).date()
            if "end_date" in opportunity_doc and opportunity_doc["end_date"]:
                opportunity_doc["end_date"] = datetime.fromisoformat(opportunity_doc["end_date"]).date()
            
            return opportunity_doc
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting opportunity by ID {opportunity_id}: {e}")
            raise DatabaseError(f"Failed to get opportunity: {str(e)}")
    
    async def update_opportunity(self, opportunity_id: str, opportunity_data: OpportunityUpdate, scout_id: str = None) -> Dict[str, Any]:
        """Update opportunity"""
        try:
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required for update")
            
            # Check ownership if scout_id provided
            if scout_id:
                opportunity = await self.get_opportunity_by_id(opportunity_id)
                if opportunity["scout_id"] != scout_id:
                    raise ValidationError("Not authorized to update this opportunity")
            
            update_data = {}
            
            if opportunity_data.title is not None:
                update_data["title"] = opportunity_data.title
            if opportunity_data.description is not None:
                update_data["description"] = opportunity_data.description
            if opportunity_data.type is not None:
                update_data["type"] = opportunity_data.type
            if opportunity_data.sport_category_id is not None:
                update_data["sport_category_id"] = opportunity_data.sport_category_id
            if opportunity_data.location is not None:
                update_data["location"] = opportunity_data.location
            if opportunity_data.start_date is not None:
                update_data["start_date"] = opportunity_data.start_date.isoformat()
            if opportunity_data.end_date is not None:
                update_data["end_date"] = opportunity_data.end_date.isoformat()
            if opportunity_data.requirements is not None:
                update_data["requirements"] = opportunity_data.requirements
            if opportunity_data.compensation is not None:
                update_data["compensation"] = opportunity_data.compensation
            if opportunity_data.is_active is not None:
                update_data["is_active"] = opportunity_data.is_active
            
            if not update_data:
                raise ValidationError("No valid fields provided for update")
            
            # Validate date range if both dates are being updated
            if opportunity_data.start_date and opportunity_data.end_date:
                if opportunity_data.end_date < opportunity_data.start_date:
                    raise ValidationError("End date cannot be before start date")
            
            try:
                await self.opportunity_service.update(opportunity_id, update_data)
            except Exception as e:
                logger.error(f"Database error updating opportunity: {e}")
                raise DatabaseError(f"Failed to update opportunity: {str(e)}")
            
            return await self.get_opportunity_by_id(opportunity_id)
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error updating opportunity {opportunity_id}: {e}")
            raise DatabaseError(f"Failed to update opportunity: {str(e)}")
    
    async def delete_opportunity(self, opportunity_id: str, scout_id: str = None) -> bool:
        """Delete opportunity"""
        try:
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required for deletion")
            
            # Check ownership if scout_id provided
            if scout_id:
                opportunity = await self.get_opportunity_by_id(opportunity_id)
                if opportunity["scout_id"] != scout_id:
                    raise ValidationError("Not authorized to delete this opportunity")
            
            try:
                await self.opportunity_service.delete(opportunity_id)
            except Exception as e:
                logger.error(f"Database error deleting opportunity: {e}")
                raise DatabaseError(f"Failed to delete opportunity: {str(e)}")
            
            return True
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error deleting opportunity {opportunity_id}: {e}")
            raise DatabaseError(f"Failed to delete opportunity: {str(e)}")
    
    async def search_opportunities(self, filters: OpportunitySearchFilters) -> PaginatedResponse:
        """Search opportunities with filters"""
        try:
            firestore_filters = [FieldFilter("is_active", "==", True)]
            
            if filters.type:
                firestore_filters.append(FieldFilter("type", "==", filters.type))
            
            if filters.location:
                firestore_filters.append(FieldFilter("location", "==", filters.location))
            
            if filters.sport_category_id:
                firestore_filters.append(FieldFilter("sport_category_id", "==", filters.sport_category_id))
            
            # Add date filters to database query if possible
            if filters.start_date:
                firestore_filters.append(FieldFilter("start_date", ">=", filters.start_date.isoformat()))
            if filters.end_date:
                firestore_filters.append(FieldFilter("start_date", "<=", filters.end_date.isoformat()))
            
            try:
                opportunities = await self.opportunity_service.query(firestore_filters, filters.limit, filters.offset)
                total_count = await self.opportunity_service.count(firestore_filters)
            except Exception as e:
                logger.error(f"Database error searching opportunities: {e}")
                raise DatabaseError(f"Failed to search opportunities: {str(e)}")
            
            # Convert date strings back to date objects
            for opportunity in opportunities:
                if "start_date" in opportunity:
                    opportunity["start_date"] = datetime.fromisoformat(opportunity["start_date"]).date()
                if "end_date" in opportunity and opportunity["end_date"]:
                    opportunity["end_date"] = datetime.fromisoformat(opportunity["end_date"]).date()
            
            return PaginatedResponse(
                count=total_count,
                results=opportunities,
                next=f"?limit={filters.limit}&offset={filters.offset + filters.limit}" if filters.offset + filters.limit < total_count else None,
                previous=f"?limit={filters.limit}&offset={max(0, filters.offset - filters.limit)}" if filters.offset > 0 else None
            )
            
        except Exception as e:
            logger.error(f"Error searching opportunities: {e}")
            raise DatabaseError(f"Failed to search opportunities: {str(e)}")
    
    async def toggle_opportunity_status(self, opportunity_id: str, toggle_data: OpportunityToggleRequest, scout_id: str = None) -> Dict[str, Any]:
        """Toggle opportunity active/inactive status"""
        try:
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required for status toggle")
            
            # Check ownership if scout_id provided
            if scout_id:
                opportunity = await self.get_opportunity_by_id(opportunity_id)
                if opportunity["scout_id"] != scout_id:
                    raise ValidationError("Not authorized to modify this opportunity")
            
            try:
                await self.opportunity_service.update(opportunity_id, {"is_active": toggle_data.is_active})
            except Exception as e:
                logger.error(f"Database error toggling opportunity status: {e}")
                raise DatabaseError(f"Failed to toggle opportunity status: {str(e)}")
            
            return await self.get_opportunity_by_id(opportunity_id)
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error toggling opportunity status {opportunity_id}: {e}")
            raise DatabaseError(f"Failed to toggle opportunity status: {str(e)}")
    
    async def apply_for_opportunity(self, opportunity_id: str, athlete_id: str, application_data: ApplicationCreate) -> Dict[str, Any]:
        """Apply for an opportunity"""
        try:
            if not opportunity_id or not athlete_id:
                raise ValidationError("Opportunity ID and Athlete ID are required for application")
            
            # Check if opportunity exists and is active
            try:
                opportunity = await self.get_opportunity_by_id(opportunity_id)
            except ResourceNotFoundError:
                raise ValidationError("Opportunity not found")
            
            if not opportunity["is_active"]:
                raise ValidationError("Opportunity is not active")
            
            # Check if already applied
            try:
                existing_applications = await self.application_service.get_by_field_list("opportunity_id", [opportunity_id])
                for app in existing_applications:
                    if app["athlete_id"] == athlete_id:
                        raise ValidationError("Already applied for this opportunity")
            except ValidationError:
                raise  # Re-raise validation errors as-is
            except Exception as e:
                logger.error(f"Database error checking existing applications: {e}")
                raise DatabaseError(f"Failed to check existing applications: {str(e)}")
            
            # Create application
            application_doc = {
                "opportunity_id": opportunity_id,
                "athlete_id": athlete_id,
                "status": "pending",
                "cover_letter": application_data.cover_letter,
                "resume_url": application_data.resume_url,
                "applied_at": datetime.now(timezone.utc)
            }
            
            try:
                application_id = await self.application_service.create(application_doc)
            except Exception as e:
                logger.error(f"Database error creating application: {e}")
                raise DatabaseError(f"Failed to create application: {str(e)}")
            
            return await self.get_application_by_id(application_id)
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error applying for opportunity {opportunity_id} by athlete {athlete_id}: {e}")
            raise DatabaseError(f"Failed to apply for opportunity: {str(e)}")
    
    async def get_opportunity_applications(self, opportunity_id: str, scout_id: str = None) -> List[Dict[str, Any]]:
        """Get applications for an opportunity"""
        try:
            if not opportunity_id:
                raise ValidationError("Opportunity ID is required")
            
            # Check ownership if scout_id provided
            if scout_id:
                opportunity = await self.get_opportunity_by_id(opportunity_id)
                if opportunity["scout_id"] != scout_id:
                    raise ValidationError("Not authorized to view applications for this opportunity")
            
            try:
                filters = [FieldFilter("opportunity_id", "==", opportunity_id)]
                applications = await self.application_service.query(filters)
            except Exception as e:
                logger.error(f"Database error getting applications: {e}")
                raise DatabaseError(f"Failed to get applications: {str(e)}")
            
            return applications
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting applications for opportunity {opportunity_id}: {e}")
            raise DatabaseError(f"Failed to get applications: {str(e)}")
    
    async def get_application_by_id(self, application_id: str) -> Optional[Dict[str, Any]]:
        """Get application by ID"""
        try:
            if not application_id:
                raise ValidationError("Application ID is required")
            
            try:
                application_doc = await self.application_service.get_by_id(application_id)
            except Exception as e:
                logger.error(f"Database error getting application: {e}")
                raise DatabaseError(f"Failed to get application: {str(e)}")
            
            if not application_doc:
                raise ResourceNotFoundError("Application", application_id)
            
            return application_doc
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error getting application by ID {application_id}: {e}")
            raise DatabaseError(f"Failed to get application: {str(e)}")
    
    async def update_application_status(self, application_id: str, status_data: ApplicationStatusUpdate, scout_id: str = None) -> Dict[str, Any]:
        """Update application status"""
        try:
            if not application_id:
                raise ValidationError("Application ID is required for status update")
            
            # Check authorization if scout_id provided
            if scout_id:
                application = await self.get_application_by_id(application_id)
                # Get opportunity to check ownership
                opportunity = await self.get_opportunity_by_id(application["opportunity_id"])
                if opportunity["scout_id"] != scout_id:
                    raise ValidationError("Not authorized to update this application")
            
            update_data = {
                "status": status_data.status,
                "status_updated_at": datetime.now(timezone.utc)
            }
            
            if status_data.feedback:
                update_data["feedback"] = status_data.feedback
            
            try:
                await self.application_service.update(application_id, update_data)
            except Exception as e:
                logger.error(f"Database error updating application status: {e}")
                raise DatabaseError(f"Failed to update application status: {str(e)}")
            
            return await self.get_application_by_id(application_id)
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error updating application status {application_id}: {e}")
            raise DatabaseError(f"Failed to update application status: {str(e)}")
    
    async def withdraw_application(self, application_id: str, athlete_id: str) -> bool:
        """Withdraw application"""
        try:
            if not application_id or not athlete_id:
                raise ValidationError("Application ID and Athlete ID are required for withdrawal")
            
            try:
                application = await self.get_application_by_id(application_id)
            except ResourceNotFoundError:
                raise ValidationError("Application not found")
            
            if application["athlete_id"] != athlete_id:
                raise ValidationError("Not authorized to withdraw this application")
            
            if application["status"] == "withdrawn":
                raise ValidationError("Application is already withdrawn")
            
            try:
                await self.application_service.update(application_id, {
                    "status": "withdrawn",
                    "status_updated_at": datetime.now(timezone.utc)
                })
            except Exception as e:
                logger.error(f"Database error withdrawing application: {e}")
                raise DatabaseError(f"Failed to withdraw application: {str(e)}")
            
            return True
            
        except (ValidationError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error withdrawing application {application_id}: {e}")
            raise DatabaseError(f"Failed to withdraw application: {str(e)}")
    
    async def get_athlete_applications(self, athlete_id: str) -> List[Dict[str, Any]]:
        """Get all applications by an athlete"""
        try:
            if not athlete_id:
                raise ValidationError("Athlete ID is required")
            
            try:
                filters = [FieldFilter("athlete_id", "==", athlete_id)]
                applications = await self.application_service.query(filters)
            except Exception as e:
                logger.error(f"Database error getting athlete applications: {e}")
                raise DatabaseError(f"Failed to get athlete applications: {str(e)}")
            
            return applications
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting applications for athlete {athlete_id}: {e}")
            raise DatabaseError(f"Failed to get athlete applications: {str(e)}")
    
    async def get_scout_opportunities(self, scout_id: str, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get opportunities created by a scout"""
        try:
            if not scout_id:
                raise ValidationError("Scout ID is required")
            
            filters = [FieldFilter("scout_id", "==", scout_id)]
            
            if status:
                filters.append(FieldFilter("is_active", "==", status == "active"))
            
            try:
                opportunities = await self.opportunity_service.query(filters, limit, offset)
            except Exception as e:
                logger.error(f"Database error getting scout opportunities: {e}")
                raise DatabaseError(f"Failed to get scout opportunities: {str(e)}")
            
            # Convert date strings back to date objects
            for opportunity in opportunities:
                if "start_date" in opportunity:
                    opportunity["start_date"] = datetime.fromisoformat(opportunity["start_date"]).date()
                if "end_date" in opportunity and opportunity["end_date"]:
                    opportunity["end_date"] = datetime.fromisoformat(opportunity["end_date"]).date()
            
            return opportunities
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error getting opportunities for scout {scout_id}: {e}")
            raise DatabaseError(f"Failed to get scout opportunities: {str(e)}") 