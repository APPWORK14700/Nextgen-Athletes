from typing import Optional, Dict, Any, List
import logging
from datetime import datetime

from ..models.conversation import Conversation, ConversationCreate, ConversationUpdate, Message, MessageCreate
from ..models.base import PaginatedResponse
from .database_service import DatabaseService
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class ConversationService:
    """Conversation service for managing messaging between athletes and scouts"""
    
    def __init__(self):
        self.conversation_service = DatabaseService("conversations")
        self.message_service = DatabaseService("messages")
    
    async def create_conversation(self, user_id: str, conversation_data: ConversationCreate) -> Dict[str, Any]:
        """Create new conversation"""
        try:
            # Check if conversation already exists between these users
            existing_conversation = await self._find_conversation_between_users(user_id, conversation_data.participant_id)
            if existing_conversation:
                # If conversation exists, just add the message
                message_doc = {
                    "conversation_id": existing_conversation["id"],
                    "sender_id": user_id,
                    "content": conversation_data.initial_message,
                    "is_read": False
                }
                
                message_id = await self.message_service.create(message_doc)
                
                # Update conversation with last message
                await self.conversation_service.update(existing_conversation["id"], {
                    "updated_at": datetime.utcnow(),
                    "last_message": await self.message_service.get_by_id(message_id)
                })
                
                return await self.get_conversation_by_id(existing_conversation["id"])
            
            # Create new conversation
            conversation_doc = {
                "participants": [user_id, conversation_data.participant_id],
                "is_archived": False
            }
            
            conversation_id = await self.conversation_service.create(conversation_doc)
            
            # Create initial message
            message_doc = {
                "conversation_id": conversation_id,
                "sender_id": user_id,
                "content": conversation_data.initial_message,
                "is_read": False
            }
            
            message_id = await self.message_service.create(message_doc)
            
            # Update conversation with last message
            await self.conversation_service.update(conversation_id, {
                "last_message": await self.message_service.get_by_id(message_id)
            })
            
            return await self.get_conversation_by_id(conversation_id)
            
        except Exception as e:
            logger.error(f"Error creating conversation for user {user_id}: {e}")
            raise
    
    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID"""
        try:
            conversation_doc = await self.conversation_service.get_by_id(conversation_id)
            return conversation_doc
            
        except Exception as e:
            logger.error(f"Error getting conversation by ID {conversation_id}: {e}")
            raise
    
    async def get_user_conversations(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all conversations for a user"""
        try:
            # Get conversations where user is a participant
            conversations = await self.conversation_service.query([], limit, offset)
            
            # Filter conversations where user is a participant
            user_conversations = []
            for conversation in conversations:
                if user_id in conversation.get("participants", []):
                    user_conversations.append(conversation)
            
            return user_conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations for user {user_id}: {e}")
            raise
    
    async def get_conversation_messages(self, conversation_id: str, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a conversation"""
        try:
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation or user_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to access this conversation")
            
            filters = [FieldFilter("conversation_id", "==", conversation_id)]
            messages = await self.message_service.query(filters, limit, offset)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages for conversation {conversation_id}: {e}")
            raise
    
    async def send_message(self, conversation_id: str, sender_id: str, message_data: MessageCreate) -> Dict[str, Any]:
        """Send message in conversation"""
        try:
            # Verify sender is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation or sender_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to send message in this conversation")
            
            # Create message
            message_doc = {
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "content": message_data.content,
                "attachment_url": message_data.attachment_url,
                "is_read": False
            }
            
            message_id = await self.message_service.create(message_doc)
            
            # Update conversation with last message
            await self.conversation_service.update(conversation_id, {
                "updated_at": datetime.utcnow(),
                "last_message": await self.message_service.get_by_id(message_id)
            })
            
            return await self.message_service.get_by_id(message_id)
            
        except Exception as e:
            logger.error(f"Error sending message in conversation {conversation_id}: {e}")
            raise
    
    async def mark_message_read(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """Mark message as read"""
        try:
            message = await self.message_service.get_by_id(message_id)
            if not message:
                raise ValueError("Message not found")
            
            # Verify user is participant in conversation
            conversation = await self.get_conversation_by_id(message["conversation_id"])
            if not conversation or user_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to mark this message as read")
            
            # Only mark as read if user is not the sender
            if message["sender_id"] != user_id:
                await self.message_service.update(message_id, {"is_read": True})
                message = await self.message_service.get_by_id(message_id)
            
            return message
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as read: {e}")
            raise
    
    async def mark_conversation_messages_read(self, conversation_id: str, user_id: str) -> bool:
        """Mark all messages in conversation as read"""
        try:
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation or user_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to access this conversation")
            
            # Get all unread messages in conversation
            filters = [
                FieldFilter("conversation_id", "==", conversation_id),
                FieldFilter("sender_id", "!=", user_id),
                FieldFilter("is_read", "==", False)
            ]
            
            unread_messages = await self.message_service.query(filters)
            
            # Mark all as read
            for message in unread_messages:
                await self.message_service.update(message["id"], {"is_read": True})
            
            return True
            
        except Exception as e:
            logger.error(f"Error marking conversation {conversation_id} messages as read: {e}")
            raise
    
    async def archive_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Archive conversation"""
        try:
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation or user_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to archive this conversation")
            
            await self.conversation_service.update(conversation_id, {"is_archived": True})
            
            return await self.get_conversation_by_id(conversation_id)
            
        except Exception as e:
            logger.error(f"Error archiving conversation {conversation_id}: {e}")
            raise
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete conversation and all messages"""
        try:
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation or user_id not in conversation.get("participants", []):
                raise ValueError("Not authorized to delete this conversation")
            
            # Delete all messages in conversation
            filters = [FieldFilter("conversation_id", "==", conversation_id)]
            messages = await self.message_service.query(filters)
            
            for message in messages:
                await self.message_service.delete(message["id"])
            
            # Delete conversation
            await self.conversation_service.delete(conversation_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            raise
    
    async def _find_conversation_between_users(self, user1_id: str, user2_id: str) -> Optional[Dict[str, Any]]:
        """Find existing conversation between two users"""
        try:
            # Get all conversations
            conversations = await self.conversation_service.query([])
            
            for conversation in conversations:
                participants = conversation.get("participants", [])
                if user1_id in participants and user2_id in participants:
                    return conversation
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding conversation between users {user1_id} and {user2_id}: {e}")
            raise
    
    async def get_unread_message_count(self, user_id: str) -> int:
        """Get count of unread messages for user"""
        try:
            # Get all conversations where user is participant
            user_conversations = await self.get_user_conversations(user_id)
            
            total_unread = 0
            for conversation in user_conversations:
                # Get unread messages in this conversation
                filters = [
                    FieldFilter("conversation_id", "==", conversation["id"]),
                    FieldFilter("sender_id", "!=", user_id),
                    FieldFilter("is_read", "==", False)
                ]
                
                unread_messages = await self.message_service.query(filters)
                total_unread += len(unread_messages)
            
            return total_unread
            
        except Exception as e:
            logger.error(f"Error getting unread message count for user {user_id}: {e}")
            raise 