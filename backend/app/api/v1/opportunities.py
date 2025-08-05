"""
Opportunities API endpoints for Athletes Networking App

This module provides endpoints for opportunity management and applications.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Form, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.api.dependencies import get_current_user, require_athlete_role, require_scout_role
from app.services.opportunity_service import OpportunityService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
logger = logging.getLogger(__name__)

# Pydantic models
class OpportunityResponse(BaseModel):
    id: str
    scout_id: str
    title: str
    description: str
    type: str
    sport_category_id: str
    location: str
    start_date: str
    end_date: Optional[str] = None
    requirements: Optional[str] = None
    compensation: Optional[str] = None
    is_active: bool
    moderation_status: str
    created_at: str

class OpportunitySearchResponse(BaseResponse):
    opportunities: List[OpportunityResponse]
    total: int

class ApplicationResponse(BaseModel):
    id: str
    opportunity_id: str
    athlete_id: str
    status: str
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    applied_at: str
    updated_at: str

# Initialize services
opportunity_service = OpportunityService()

@router.post("/", response_model=OpportunityResponse)
async def create_opportunity(
    title: str = Form(...),
    description: str = Form(...),
    type: str = Form(...),
    sport_category_id: str = Form(...),
    location: str = Form(...),
    start_date: str = Form(...),
    end_date: Optional[str] = Form(None),
    requirements: Optional[str] = Form(None),
    compensation: Optional[str] = Form(None),
    current_user: dict = Depends(require_scout_role)
):
    """Create a new opportunity"""
    try:
        opportunity_data = {
            "title": title,
            "description": description,
            "type": type,
            "sport_category_id": sport_category_id,
            "location": location,
            "start_date": start_date,
            "end_date": end_date,
            "requirements": requirements,
            "compensation": compensation,
            "scout_id": current_user["uid"]
        }
        
        result = await opportunity_service.create_opportunity(opportunity_data)
        logger.info(f"Opportunity created by scout {current_user['uid']}")
        return OpportunityResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=OpportunitySearchResponse)
async def list_opportunities(
    type: Optional[str] = Query(None, description="Opportunity type filter"),
    location: Optional[str] = Query(None, description="Location filter"),
    sport_category_id: Optional[str] = Query(None, description="Sport category filter"),
    is_active: bool = Query(True, description="Show only active opportunities"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """List all available opportunities with filters"""
    try:
        filters = {"is_active": is_active}
        
        if type:
            filters["type"] = type
        if location:
            filters["location"] = location
        if sport_category_id:
            filters["sport_category_id"] = sport_category_id
        
        # Only show approved opportunities to athletes
        user_role = current_user.get("role")
        if user_role == "athlete":
            filters["moderation_status"] = "approved"
        
        result = await opportunity_service.search_opportunities(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return OpportunitySearchResponse(
            opportunities=[OpportunityResponse(**opp) for opp in result["opportunities"]],
            total=result["total"]
        )
        
    except Exception as e:
        logger.error(f"Error listing opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(
    opportunity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific opportunity"""
    try:
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        
        # Check if user can access this opportunity
        user_role = current_user.get("role")
        if user_role == "athlete" and opportunity.get("moderation_status") != "approved":
            raise AuthorizationError("Opportunity not available")
        
        return OpportunityResponse(**opportunity)
        
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{opportunity_id}", response_model=OpportunityResponse)
async def update_opportunity(
    opportunity_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    requirements: Optional[str] = Form(None),
    compensation: Optional[str] = Form(None),
    current_user: dict = Depends(require_scout_role)
):
    """Update an opportunity"""
    try:
        # Verify ownership
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        if opportunity["scout_id"] != current_user["uid"]:
            raise AuthorizationError("You can only update your own opportunities")
        
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if description is not None:
            update_data["description"] = description
        if type is not None:
            update_data["type"] = type
        if location is not None:
            update_data["location"] = location
        if start_date is not None:
            update_data["start_date"] = start_date
        if end_date is not None:
            update_data["end_date"] = end_date
        if requirements is not None:
            update_data["requirements"] = requirements
        if compensation is not None:
            update_data["compensation"] = compensation
        
        result = await opportunity_service.update_opportunity(opportunity_id, update_data)
        logger.info(f"Opportunity {opportunity_id} updated by scout {current_user['uid']}")
        return OpportunityResponse(**result)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{opportunity_id}", status_code=204)
async def delete_opportunity(
    opportunity_id: str,
    current_user: dict = Depends(require_scout_role)
):
    """Delete an opportunity"""
    try:
        # Verify ownership
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        if opportunity["scout_id"] != current_user["uid"]:
            raise AuthorizationError("You can only delete your own opportunities")
        
        await opportunity_service.delete_opportunity(opportunity_id)
        logger.info(f"Opportunity {opportunity_id} deleted by scout {current_user['uid']}")
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except Exception as e:
        logger.error(f"Error deleting opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# NEW MISSING ENDPOINT - Toggle Status

@router.put("/{opportunity_id}/toggle-status", response_model=OpportunityResponse)
async def toggle_opportunity_status(
    opportunity_id: str,
    current_user: dict = Depends(require_scout_role)
):
    """
    Toggle opportunity active/inactive status
    Only the opportunity owner (scout) can toggle status
    """
    try:
        # Verify ownership
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        if opportunity["scout_id"] != current_user["uid"]:
            raise AuthorizationError("You can only toggle status of your own opportunities")
        
        # Toggle the status
        new_status = not opportunity.get("is_active", True)
        update_data = {"is_active": new_status}
        
        result = await opportunity_service.update_opportunity(opportunity_id, update_data)
        
        status_text = "activated" if new_status else "deactivated"
        logger.info(f"Opportunity {opportunity_id} {status_text} by scout {current_user['uid']}")
        
        return OpportunityResponse(**result)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except Exception as e:
        logger.error(f"Error toggling opportunity status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{opportunity_id}/apply", response_model=ApplicationResponse)
async def apply_for_opportunity(
    opportunity_id: str,
    cover_letter: Optional[str] = Form(None),
    resume_url: Optional[str] = Form(None),
    current_user: dict = Depends(require_athlete_role)
):
    """Apply for an opportunity"""
    try:
        application_data = {
            "opportunity_id": opportunity_id,
            "athlete_id": current_user["uid"],
            "cover_letter": cover_letter,
            "resume_url": resume_url
        }
        
        result = await opportunity_service.apply_for_opportunity(application_data)
        logger.info(f"Application submitted for opportunity {opportunity_id} by athlete {current_user['uid']}")
        return ApplicationResponse(**result)
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except Exception as e:
        logger.error(f"Error applying for opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{opportunity_id}/applications", response_model=List[ApplicationResponse])
async def get_opportunity_applications(
    opportunity_id: str,
    status: Optional[str] = Query(None, description="Application status filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_scout_role)
):
    """Get applications for an opportunity (scout owner only)"""
    try:
        # Verify ownership
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        if opportunity["scout_id"] != current_user["uid"]:
            raise AuthorizationError("You can only view applications for your own opportunities")
        
        filters = {"opportunity_id": opportunity_id}
        if status:
            filters["status"] = status
        
        applications = await opportunity_service.get_applications(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return [ApplicationResponse(**app) for app in applications]
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    except Exception as e:
        logger.error(f"Error getting opportunity applications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{opportunity_id}/applications/{application_id}", response_model=ApplicationResponse)
async def update_application_status(
    opportunity_id: str,
    application_id: str,
    status: str = Form(...),
    feedback: Optional[str] = Form(None),
    current_user: dict = Depends(require_scout_role)
):
    """Update application status (accept/reject)"""
    try:
        # Verify opportunity ownership
        opportunity = await opportunity_service.get_opportunity_by_id(opportunity_id)
        if opportunity["scout_id"] != current_user["uid"]:
            raise AuthorizationError("You can only update applications for your own opportunities")
        
        update_data = {
            "status": status,
            "feedback": feedback
        }
        
        result = await opportunity_service.update_application_status(application_id, update_data)
        logger.info(f"Application {application_id} status updated to {status} by scout {current_user['uid']}")
        return ApplicationResponse(**result)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Application not found")
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/my/applications", response_model=List[ApplicationResponse])
async def get_my_applications(
    status: Optional[str] = Query(None, description="Application status filter"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete_role)
):
    """Get all applications submitted by the athlete"""
    try:
        filters = {"athlete_id": current_user["uid"]}
        if status:
            filters["status"] = status
        
        applications = await opportunity_service.get_applications(
            filters=filters,
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return [ApplicationResponse(**app) for app in applications]
        
    except Exception as e:
        logger.error(f"Error getting athlete applications: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/my/applications/{application_id}", response_model=ApplicationResponse)
async def get_my_application(
    application_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Get details of a specific application submitted by the athlete"""
    try:
        application = await opportunity_service.get_application_by_id(application_id)
        
        # Verify ownership
        if application["athlete_id"] != current_user["uid"]:
            raise AuthorizationError("You can only view your own applications")
        
        return ApplicationResponse(**application)
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Application not found")
    except Exception as e:
        logger.error(f"Error getting application: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/my/applications/{application_id}", status_code=204)
async def withdraw_application(
    application_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Withdraw an application (athlete applicant only)"""
    try:
        application = await opportunity_service.get_application_by_id(application_id)
        
        # Verify ownership
        if application["athlete_id"] != current_user["uid"]:
            raise AuthorizationError("You can only withdraw your own applications")
        
        await opportunity_service.withdraw_application(application_id)
        logger.info(f"Application {application_id} withdrawn by athlete {current_user['uid']}")
        
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Application not found")
    except Exception as e:
        logger.error(f"Error withdrawing application: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/recommended", response_model=List[OpportunityResponse])
async def get_recommended_opportunities(
    sport: Optional[str] = Query(None, description="Sport filter"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete_role)
):
    """Get recommended opportunities for authenticated athlete"""
    try:
        recommendations = await opportunity_service.get_recommended_opportunities(
            athlete_id=current_user["uid"],
            sport=sport,
            limit=limit,
            offset=offset
        )
        
        return [OpportunityResponse(**opp) for opp in recommendations]
        
    except Exception as e:
        logger.error(f"Error getting recommended opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{opportunity_id}/save")
async def save_opportunity(
    opportunity_id: str,
    current_user: dict = Depends(require_athlete_role)
):
    """Save opportunity for later"""
    try:
        result = await opportunity_service.save_opportunity(
            opportunity_id=opportunity_id,
            athlete_id=current_user["uid"]
        )
        logger.info(f"Opportunity {opportunity_id} saved by athlete {current_user['uid']}")
        return {"message": "Opportunity saved successfully", "saved_id": result["id"]}
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/saved", response_model=List[OpportunityResponse])
async def get_saved_opportunities(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_athlete_role)
):
    """Get saved opportunities for authenticated athlete"""
    try:
        saved_opportunities = await opportunity_service.get_saved_opportunities(
            athlete_id=current_user["uid"],
            page=(offset // limit) + 1,
            limit=limit
        )
        
        return [OpportunityResponse(**opp) for opp in saved_opportunities]
        
    except Exception as e:
        logger.error(f"Error getting saved opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{opportunity_id}/share")
async def share_opportunity(
    opportunity_id: str,
    target_user_id: str = Form(...),
    message: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Share opportunity with another user"""
    try:
        result = await opportunity_service.share_opportunity(
            opportunity_id=opportunity_id,
            from_user_id=current_user["uid"],
            to_user_id=target_user_id,
            message=message
        )
        logger.info(f"Opportunity {opportunity_id} shared by user {current_user['uid']} with user {target_user_id}")
        return {"message": "Opportunity shared successfully", "share_id": result["id"]}
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sharing opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/shared", response_model=List[OpportunityResponse])
async def get_shared_opportunities(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get opportunities shared with authenticated user"""
    try:
        shared_opportunities = await opportunity_service.get_shared_opportunities(
            user_id=current_user["uid"],
            page=(offset // limit) + 1,
            limit=limit
        )
        return [OpportunityResponse(**opp) for opp in shared_opportunities]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting shared opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stats/overview")
async def get_opportunity_stats(
    current_user: dict = Depends(require_scout_role)
):
    """Get opportunity statistics for current scout"""
    try:
        stats = await opportunity_service.get_scout_opportunity_stats(
            scout_id=current_user["uid"]
        )
        return stats
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting opportunity stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 