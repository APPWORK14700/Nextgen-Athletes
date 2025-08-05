"""
Conversations API endpoints for Athletes Networking App

This module provides endpoints for messaging and conversations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Form, Query, HTTPException, status
from pydantic import BaseModel, Field
import logging

from app.api.dependencies import get_current_user
from app.services.conversation_service import ConversationService
from app.models.base import BaseResponse
from app.api.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = logging.getLogger(__name__)

# Pydantic models
class ConversationResponse(BaseModel):
    id: str
    participants: List[str]
    is_archived: bool
    created_at: str
    updated_at: str
    last_message: Optional[dict] = None

class ConversationListResponse(BaseResponse):
    conversations: List[ConversationResponse]

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    attachment_url: Optional[str] = None
    is_read: bool
    created_at: str

class MessageListResponse(BaseResponse):
    messages: List[MessageResponse]

# Initialize services
conversation_service = ConversationService()

@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    participant_id: str = Form(...),
    initial_message: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation"""
    try:
        conversation = await conversation_service.create_conversation(
            creator_id=current_user["uid"],
            participant_id=participant_id,
            initial_message=initial_message
        )
        logger.info(f"Conversation created between {current_user['uid']} and {participant_id}")
        return ConversationResponse(**conversation)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=ConversationListResponse)
async def get_conversations(
    archived: Optional[bool] = Query(None, description="Filter by archived status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get all conversations for current user"""
    try:
        conversations = await conversation_service.get_user_conversations(
            user_id=current_user["uid"],
            archived=archived,
            page=(offset // limit) + 1,
            limit=limit
        )
        return ConversationListResponse(
            conversations=[ConversationResponse(**conv) for conv in conversations["conversations"]]
        )
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific conversation"""
    try:
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        return ConversationResponse(**conversation)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except AuthorizationError:
        raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete conversation and all messages"""
    try:
        await conversation_service.delete_conversation(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Conversation {conversation_id} deleted by user {current_user['uid']}")
        return {"message": "Conversation deleted successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Archive conversation"""
    try:
        result = await conversation_service.archive_conversation(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Conversation {conversation_id} archived by user {current_user['uid']}")
        return result
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error archiving conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/unarchive")
async def unarchive_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Unarchive conversation"""
    try:
        result = await conversation_service.unarchive_conversation(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Conversation {conversation_id} unarchived by user {current_user['uid']}")
        return result
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unarchiving conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/mark-read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark entire conversation as read"""
    try:
        await conversation_service.mark_conversation_read(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Conversation {conversation_id} marked as read by user {current_user['uid']}")
        return {"message": "Conversation marked as read"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking conversation as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    content: str = Form(...),
    attachment_url: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Send message in conversation"""
    try:
        message = await conversation_service.send_message(
            conversation_id=conversation_id,
            sender_id=current_user["uid"],
            content=content,
            attachment_url=attachment_url
        )
        logger.info(f"Message sent in conversation {conversation_id} by user {current_user['uid']}")
        return MessageResponse(**message)
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """Get messages for conversation"""
    try:
        messages = await conversation_service.get_messages(
            conversation_id=conversation_id,
            user_id=current_user["uid"],
            page=(offset // limit) + 1,
            limit=limit
        )
        return MessageListResponse(
            messages=[MessageResponse(**msg) for msg in messages["messages"]]
        )
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{conversation_id}/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific message"""
    try:
        message = await conversation_service.get_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"]
        )
        return MessageResponse(**message)
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{conversation_id}/messages/{message_id}", response_model=MessageResponse)
async def update_message(
    conversation_id: str,
    message_id: str,
    content: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Update message content"""
    try:
        message = await conversation_service.update_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"],
            content=content
        )
        logger.info(f"Message {message_id} updated by user {current_user['uid']}")
        return MessageResponse(**message)
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete message"""
    try:
        await conversation_service.delete_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Message {message_id} deleted by user {current_user['uid']}")
        return {"message": "Message deleted successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/messages/{message_id}/read")
async def mark_message_read(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark message as read"""
    try:
        await conversation_service.mark_message_read(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Message {message_id} marked as read by user {current_user['uid']}")
        return {"message": "Message marked as read"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking message as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# NEW MISSING ENDPOINTS - Message Read Management as specified in API spec

@router.put("/{conversation_id}/messages/{message_id}/read")
async def mark_specific_message_read(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a specific message as read (PUT version as per API specification)
    """
    try:
        message = await conversation_service.mark_message_read(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Message {message_id} marked as read by user {current_user['uid']}")
        return MessageResponse(**message)
    except (ResourceNotFoundError, AuthorizationError) as e:
        status_code = 404 if isinstance(e, ResourceNotFoundError) else 403
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking message as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{conversation_id}/messages/read-all")
async def mark_all_messages_read(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark all messages in a conversation as read
    """
    try:
        await conversation_service.mark_all_messages_read(
            conversation_id=conversation_id,
            user_id=current_user["uid"]
        )
        logger.info(f"All messages in conversation {conversation_id} marked as read by user {current_user['uid']}")
        return {"message": "All messages marked as read"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        status_code = 404 if isinstance(e, ResourceNotFoundError) else 403
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking all messages as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/messages/{message_id}/react")
async def react_to_message(
    conversation_id: str,
    message_id: str,
    reaction: str = Form(..., description="Reaction emoji"),
    current_user: dict = Depends(get_current_user)
):
    """React to message"""
    try:
        result = await conversation_service.react_to_message(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"],
            reaction=reaction
        )
        logger.info(f"Reaction {reaction} added to message {message_id} by user {current_user['uid']}")
        return result
    except (ValidationError, ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reacting to message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{conversation_id}/messages/{message_id}/react")
async def remove_reaction(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove reaction from message"""
    try:
        await conversation_service.remove_reaction(
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user["uid"]
        )
        logger.info(f"Reaction removed from message {message_id} by user {current_user['uid']}")
        return {"message": "Reaction removed successfully"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing reaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/unread/count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user)
):
    """Get unread conversation count"""
    try:
        count = await conversation_service.get_unread_count(current_user["uid"])
        return {"unread_count": count}
    except Exception as e:
        logger.error(f"Error getting unread count: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/{conversation_id}/typing")
async def send_typing_indicator(
    conversation_id: str,
    is_typing: bool = Form(..., description="Typing status"),
    current_user: dict = Depends(get_current_user)
):
    """Send typing indicator"""
    try:
        await conversation_service.send_typing_indicator(
            conversation_id=conversation_id,
            user_id=current_user["uid"],
            is_typing=is_typing
        )
        status = "started" if is_typing else "stopped"
        logger.info(f"Typing {status} in conversation {conversation_id} by user {current_user['uid']}")
        return {"message": f"Typing indicator {status}"}
    except (ResourceNotFoundError, AuthorizationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending typing indicator: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/search")
async def search_conversations(
    query: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """Search conversations and messages"""
    try:
        results = await conversation_service.search_conversations(
            user_id=current_user["uid"],
            query=query,
            page=page,
            limit=limit
        )
        return results
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 