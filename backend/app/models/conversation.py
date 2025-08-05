from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import BaseModelWithID


class Message(BaseModelWithID):
    """Message model for conversations"""
    conversation_id: str
    sender_id: str
    content: str
    attachment_url: Optional[str] = None
    is_read: bool = False


class MessageCreate(BaseModel):
    """Model for creating message"""
    content: str
    attachment_url: Optional[str] = None


class Conversation(BaseModelWithID):
    """Conversation model between athletes and scouts"""
    participants: List[str]
    is_archived: bool = False
    last_message: Optional[Message] = None


class ConversationCreate(BaseModel):
    """Model for creating conversation"""
    participant_id: str
    initial_message: str


class ConversationUpdate(BaseModel):
    """Model for updating conversation"""
    is_archived: Optional[bool] = None


class MessageReadRequest(BaseModel):
    """Model for marking message as read"""
    message_id: str 