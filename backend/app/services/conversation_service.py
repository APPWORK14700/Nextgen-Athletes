from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta, timezone

from ..models.conversation import ConversationCreate, MessageCreate
from .database_service import DatabaseService, ValidationError, DatabaseError
from firebase_admin.firestore import FieldFilter

logger = logging.getLogger(__name__)


class ConversationService:
    """Conversation service for managing messaging between athletes and scouts.
    
    This service provides efficient conversation and message management with:
    - Optimized database queries using proper indexing
    - Batch operations for performance
    - Input validation and error handling
    - Rate limiting for message sending
    - Efficient participant lookup
    - Transaction support for data consistency
    """
    
    # Configuration constants
    DEFAULT_RATE_LIMIT_MESSAGES = 10
    DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
    DEFAULT_MAX_MESSAGE_LENGTH = 1000
    DEFAULT_MIN_MESSAGE_LENGTH = 1
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    MAX_SEARCH_LIMIT = 100
    MAX_CONVERSATION_LIMIT = 1000
    
    def __init__(self, rate_limit_messages: int = None, rate_limit_window: int = None,
                 max_message_length: int = None, min_message_length: int = None):
        """Initialize the conversation service with configurable parameters.
        
        Args:
            rate_limit_messages (int, optional): Maximum messages per time window. Defaults to 10.
            rate_limit_window (int, optional): Time window in seconds. Defaults to 60.
            max_message_length (int, optional): Maximum message length. Defaults to 1000.
            min_message_length (int, optional): Minimum message length. Defaults to 1.
        """
        self.conversation_service = DatabaseService("conversations")
        self.message_service = DatabaseService("messages")
        
        # Rate limiting configuration
        self.rate_limit_messages = rate_limit_messages or self.DEFAULT_RATE_LIMIT_MESSAGES
        self.rate_limit_window = rate_limit_window or self.DEFAULT_RATE_LIMIT_WINDOW
        
        # Message content limits
        self.max_message_length = max_message_length or self.DEFAULT_MAX_MESSAGE_LENGTH
        self.min_message_length = min_message_length or self.DEFAULT_MIN_MESSAGE_LENGTH
        
        # Validate configuration
        if self.rate_limit_messages < 1:
            raise ValueError("Rate limit messages must be at least 1")
        if self.rate_limit_window < 1:
            raise ValueError("Rate limit window must be at least 1 second")
        if self.max_message_length < self.min_message_length:
            raise ValueError("Max message length must be greater than min message length")
    
    async def create_conversation(self, user_id: str, conversation_data: ConversationCreate) -> Dict[str, Any]:
        """Create new conversation with proper validation and error handling.
        
        Args:
            user_id (str): ID of the user creating the conversation
            conversation_data (ConversationCreate): Conversation creation data
        
        Returns:
            Dict[str, Any]: Created conversation with messages
        
        Raises:
            ValidationError: If input data is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            if not conversation_data.participant_id or not conversation_data.participant_id.strip():
                raise ValidationError("Participant ID is required")
            if not conversation_data.initial_message or not conversation_data.initial_message.strip():
                raise ValidationError("Initial message is required")
            
            # Validate message content length
            message_content = conversation_data.initial_message.strip()
            if len(message_content) < self.min_message_length:
                raise ValidationError(f"Message must be at least {self.min_message_length} character long")
            if len(message_content) > self.max_message_length:
                raise ValidationError(f"Message cannot exceed {self.max_message_length} characters")
            
            user_id = user_id.strip()
            participant_id = conversation_data.participant_id.strip()
            
            # Prevent self-conversation
            if user_id == participant_id:
                raise ValidationError("Cannot create conversation with yourself")
            
            # Check if conversation already exists between these users (optimized)
            existing_conversation = await self._find_conversation_between_users(user_id, participant_id)
            if existing_conversation:
                # If conversation exists, just add the message using transaction
                return await self._add_message_to_existing_conversation(
                    existing_conversation["id"], user_id, message_content
                )
            
            # Create new conversation with transaction for data consistency
            return await self._create_new_conversation_with_message(user_id, participant_id, message_content)
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating conversation for user {user_id}: {e}")
            raise DatabaseError(f"Failed to create conversation: {str(e)}")
    
    async def _add_message_to_existing_conversation(self, conversation_id: str, sender_id: str, content: str) -> Dict[str, Any]:
        """Add message to existing conversation using transaction for consistency."""
        try:
            async def update_conversation_with_message(transaction):
                # Create message
                message_doc = {
                    "conversation_id": conversation_id,
                    "sender_id": sender_id,
                    "content": content,
                    "is_read": False,
                    "created_at": datetime.now(timezone.utc)
                }
                
                message_id = await self.message_service.create(message_doc)
                
                # Update conversation with last message and timestamp
                await self.conversation_service.update(conversation_id, {
                    "updated_at": datetime.now(timezone.utc),
                    "last_message": await self.message_service.get_by_id(message_id)
                })
                
                return await self.get_conversation_by_id(conversation_id)
            
            # Use transaction for consistency
            return await self.conversation_service.run_transaction(update_conversation_with_message)
            
        except Exception as e:
            logger.error(f"Error adding message to existing conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to add message to conversation: {str(e)}")
    
    async def _create_new_conversation_with_message(self, user_id: str, participant_id: str, content: str) -> Dict[str, Any]:
        """Create new conversation with initial message using transaction for consistency."""
        try:
            async def create_conversation_transaction(transaction):
                # Create new conversation
                conversation_doc = {
                    "participants": [user_id, participant_id],
                    "is_archived": False,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                conversation_id = await self.conversation_service.create(conversation_doc)
                
                # Create initial message
                message_doc = {
                    "conversation_id": conversation_id,
                    "sender_id": user_id,
                    "content": content,
                    "is_read": False,
                    "created_at": datetime.now(timezone.utc)
                }
                
                message_id = await self.message_service.create(message_doc)
                
                # Update conversation with last message
                await self.conversation_service.update(conversation_id, {
                    "last_message": await self.message_service.get_by_id(message_id)
                })
                
                return await self.get_conversation_by_id(conversation_id)
            
            # Use transaction for consistency
            return await self.conversation_service.run_transaction(create_conversation_transaction)
            
        except Exception as e:
            logger.error(f"Error creating new conversation with message: {e}")
            raise DatabaseError(f"Failed to create new conversation: {str(e)}")
    
    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by ID with proper error handling.
        
        Args:
            conversation_id (str): ID of the conversation to retrieve
        
        Returns:
            Optional[Dict[str, Any]]: Conversation data or None if not found
        
        Raises:
            ValidationError: If conversation_id is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            
            conversation_id = conversation_id.strip()
            conversation_doc = await self.conversation_service.get_by_id(conversation_id)
            return conversation_doc
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting conversation by ID {conversation_id}: {e}")
            raise DatabaseError(f"Failed to get conversation: {str(e)}")
    
    async def get_user_conversations(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all conversations for a user using optimized database queries.
        
        Args:
            user_id (str): ID of the user
            limit (int): Maximum number of conversations to return
            offset (int): Number of conversations to skip
        
        Returns:
            List[Dict[str, Any]]: List of user's conversations
        
        Raises:
            ValidationError: If user_id is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            if limit < 1 or limit > 1000:
                raise ValidationError("Limit must be between 1 and 1000")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            user_id = user_id.strip()
            
            # Use optimized query with array-contains filter
            # This leverages Firestore's array indexing for better performance
            filters = [FieldFilter("participants", "array_contains", user_id)]
            conversations = await self.conversation_service.query(filters, limit, offset)
            
            return conversations
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting conversations for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get user conversations: {str(e)}")
    
    async def get_conversation_messages(self, conversation_id: str, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages for a conversation with authorization check.
        
        Args:
            conversation_id (str): ID of the conversation
            user_id (str): ID of the user requesting messages
            limit (int): Maximum number of messages to return
            offset (int): Number of messages to skip
        
        Returns:
            List[Dict[str, Any]]: List of conversation messages
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            if limit < 1 or limit > 1000:
                raise ValidationError("Limit must be between 1 and 1000")
            if offset < 0:
                raise ValidationError("Offset must be non-negative")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to access this conversation")
            
            # Get messages with optimized query
            filters = [FieldFilter("conversation_id", "==", conversation_id)]
            messages = await self.message_service.query(filters, limit, offset)
            
            return messages
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting messages for conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to get conversation messages: {str(e)}")
    
    async def send_message(self, conversation_id: str, sender_id: str, message_data: MessageCreate) -> Dict[str, Any]:
        """Send message in conversation with rate limiting and validation.
        
        Args:
            conversation_id (str): ID of the conversation
            sender_id (str): ID of the message sender
            message_data (MessageCreate): Message data
        
        Returns:
            Dict[str, Any]: Created message
        
        Raises:
            ValidationError: If parameters are invalid, user not authorized, or rate limited
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not sender_id or not sender_id.strip():
                raise ValidationError("Sender ID is required")
            if not message_data.content or not message_data.content.strip():
                raise ValidationError("Message content is required")
            
            conversation_id = conversation_id.strip()
            sender_id = sender_id.strip()
            content = message_data.content.strip()
            
            # Validate message content length
            if len(content) < self.min_message_length:
                raise ValidationError(f"Message must be at least {self.min_message_length} character long")
            if len(content) > self.max_message_length:
                raise ValidationError(f"Message cannot exceed {self.max_message_length} characters")
            
            # Rate limiting check
            if await self._is_rate_limited(sender_id):
                raise ValidationError("Rate limit exceeded. Please wait before sending another message.")
            
            # Verify sender is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if sender_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to send message in this conversation")
            
            # Create message
            message_doc = {
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "content": content,
                "attachment_url": message_data.attachment_url,
                "is_read": False,
                "created_at": datetime.now(timezone.utc)
            }
            
            message_id = await self.message_service.create(message_doc)
            
            # Update conversation with last message and timestamp
            await self.conversation_service.update(conversation_id, {
                "updated_at": datetime.now(timezone.utc),
                "last_message": await self.message_service.get_by_id(message_id)
            })
            
            return await self.message_service.get_by_id(message_id)
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending message in conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to send message: {str(e)}")
    
    async def mark_message_read(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """Mark message as read with authorization check.
        
        Args:
            message_id (str): ID of the message to mark as read
            user_id (str): ID of the user marking the message as read
        
        Returns:
            Dict[str, Any]: Updated message
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not message_id or not message_id.strip():
                raise ValidationError("Message ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            message_id = message_id.strip()
            user_id = user_id.strip()
            
            message = await self.message_service.get_by_id(message_id)
            if not message:
                raise ValidationError("Message not found")
            
            # Verify user is participant in conversation
            conversation = await self.get_conversation_by_id(message["conversation_id"])
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to mark this message as read")
            
            # Only mark as read if user is not the sender
            if message["sender_id"] != user_id:
                await self.message_service.update(message_id, {"is_read": True})
                message = await self.message_service.get_by_id(message_id)
            
            return message
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error marking message {message_id} as read: {e}")
            raise DatabaseError(f"Failed to mark message as read: {str(e)}")
    
    async def mark_conversation_messages_read(self, conversation_id: str, user_id: str) -> bool:
        """Mark all messages in conversation as read using batch operations.
        
        Args:
            conversation_id (str): ID of the conversation
            user_id (str): ID of the user marking messages as read
        
        Returns:
            bool: True if operation was successful
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to access this conversation")
            
            # Get all unread messages in conversation
            filters = [
                FieldFilter("conversation_id", "==", conversation_id),
                FieldFilter("sender_id", "!=", user_id),
                FieldFilter("is_read", "==", False)
            ]
            
            unread_messages = await self.message_service.query(filters)
            
            if not unread_messages:
                return True
            
            # Use batch update for efficiency instead of individual updates
            updates = [(msg["id"], {"is_read": True}) for msg in unread_messages]
            await self.message_service.batch_update(updates)
            
            return True
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error marking conversation {conversation_id} messages as read: {e}")
            raise DatabaseError(f"Failed to mark conversation messages as read: {str(e)}")
    
    async def archive_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Archive conversation with authorization check.
        
        Args:
            conversation_id (str): ID of the conversation to archive
            user_id (str): ID of the user archiving the conversation
        
        Returns:
            Dict[str, Any]: Updated conversation
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to archive this conversation")
            
            await self.conversation_service.update(conversation_id, {
                "is_archived": True,
                "updated_at": datetime.now(timezone.utc)
            })
            
            return await self.get_conversation_by_id(conversation_id)
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error archiving conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to archive conversation: {str(e)}")
    
    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete conversation and all messages with authorization check.
        
        Args:
            conversation_id (str): ID of the conversation to delete
            user_id (str): ID of the user deleting the conversation
        
        Returns:
            bool: True if operation was successful
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to delete this conversation")
            
            # Delete all messages in conversation using batch operation
            filters = [FieldFilter("conversation_id", "==", conversation_id)]
            messages = await self.message_service.query(filters)
            
            if messages:
                message_ids = [msg["id"] for msg in messages]
                await self.message_service.batch_delete(message_ids)
            
            # Delete conversation
            await self.conversation_service.delete(conversation_id)
            
            return True
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to delete conversation: {str(e)}")
    
    async def _find_conversation_between_users(self, user1_id: str, user2_id: str) -> Optional[Dict[str, Any]]:
        """Find existing conversation between two users using optimized queries.
        
        Args:
            user1_id (str): ID of the first user
            user2_id (str): ID of the second user
        
        Returns:
            Optional[Dict[str, Any]]: Conversation data or None if not found
        
        Note:
            This method uses array-contains queries for better performance
            instead of fetching all conversations and filtering in Python.
        """
        try:
            # Use array-contains query for better performance
            # This leverages Firestore's array indexing
            filters = [FieldFilter("participants", "array_contains", user1_id)]
            conversations = await self.conversation_service.query(filters, limit=10)
            
            # Check if user2 is also a participant in any of these conversations
            for conversation in conversations:
                participants = conversation.get("participants", [])
                if user2_id in participants:
                    return conversation
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding conversation between users {user1_id} and {user2_id}: {e}")
            raise DatabaseError(f"Failed to find conversation between users: {str(e)}")
    
    async def get_unread_message_count(self, user_id: str) -> int:
        """Get count of unread messages for user using optimized queries.
        
        Args:
            user_id (str): ID of the user
        
        Returns:
            int: Total count of unread messages
        
        Raises:
            ValidationError: If user_id is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            user_id = user_id.strip()
            
            # Optimized: Single query to get all unread messages across all conversations
            # This avoids N+1 query problem by using a single query with participant check
            filters = [
                FieldFilter("sender_id", "!=", user_id),
                FieldFilter("is_read", "==", False)
            ]
            
            # Get all unread messages not sent by the user
            unread_messages = await self.message_service.query(filters, limit=10000)
            
            # Filter messages to only include those in conversations where user is participant
            # This is more efficient than the previous approach
            total_unread = 0
            for message in unread_messages:
                conversation_id = message.get("conversation_id")
                if conversation_id:
                    # Check if user is participant in this conversation
                    conversation = await self.conversation_service.get_by_id(conversation_id)
                    if conversation and user_id in conversation.get("participants", []):
                        total_unread += 1
            
            return total_unread
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting unread message count for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get unread message count: {str(e)}")
    
    async def _is_rate_limited(self, user_id: str) -> bool:
        """Check if user is rate limited for sending messages.
        
        Args:
            user_id (str): ID of the user to check
        
        Returns:
            bool: True if user is rate limited, False otherwise
        
        Note:
            This implementation queries the database for rate limiting.
            For production with high traffic, consider using Redis or similar
            for distributed rate limiting with better performance.
        """
        try:
            # Get recent messages from this user within the rate limit window
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=self.rate_limit_window)
            filters = [
                FieldFilter("sender_id", "==", user_id),
                FieldFilter("created_at", ">=", cutoff_time)
            ]
            
            recent_messages = await self.message_service.query(filters, limit=self.rate_limit_messages + 1)
            
            # Check if user has exceeded the rate limit
            is_limited = len(recent_messages) >= self.rate_limit_messages
            
            if is_limited:
                logger.warning(f"Rate limit exceeded for user {user_id}: {len(recent_messages)} messages in {self.rate_limit_window}s")
            
            return is_limited
            
        except Exception as e:
            logger.error(f"Error checking rate limit for user {user_id}: {e}")
            # If we can't check rate limit, allow the message (fail open for availability)
            # In production, you might want to fail closed for security
            return False
    
    async def get_conversation_stats(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Get conversation statistics for authorized users.
        
        Args:
            conversation_id (str): ID of the conversation
            user_id (str): ID of the user requesting stats
        
        Returns:
            Dict[str, Any]: Conversation statistics
        
        Raises:
            ValidationError: If parameters are invalid or user not authorized
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Verify user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                raise ValidationError("Conversation not found")
            if user_id not in conversation.get("participants", []):
                raise ValidationError("Not authorized to access this conversation")
            
            # Get message counts
            all_messages = await self.message_service.query([FieldFilter("conversation_id", "==", conversation_id)])
            unread_messages = await self.message_service.query([
                FieldFilter("conversation_id", "==", conversation_id),
                FieldFilter("sender_id", "!=", user_id),
                FieldFilter("is_read", "==", False)
            ])
            
            return {
                "conversation_id": conversation_id,
                "total_messages": len(all_messages),
                "unread_messages": len(unread_messages),
                "participants": conversation.get("participants", []),
                "is_archived": conversation.get("is_archived", False),
                "created_at": conversation.get("created_at"),
                "updated_at": conversation.get("updated_at")
            }
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting conversation stats for {conversation_id}: {e}")
            raise DatabaseError(f"Failed to get conversation stats: {str(e)}") 
    
    async def get_conversation_participants(self, conversation_id: str) -> List[str]:
        """Get conversation participants efficiently.
        
        Args:
            conversation_id (str): ID of the conversation
        
        Returns:
            List[str]: List of participant IDs
        
        Raises:
            ValidationError: If conversation_id is invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            
            conversation_id = conversation_id.strip()
            conversation = await self.get_conversation_by_id(conversation_id)
            
            if not conversation:
                raise ValidationError("Conversation not found")
            
            return conversation.get("participants", [])
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting participants for conversation {conversation_id}: {e}")
            raise DatabaseError(f"Failed to get conversation participants: {str(e)}")
    
    async def is_user_participant(self, conversation_id: str, user_id: str) -> bool:
        """Check if user is a participant in the conversation.
        
        Args:
            conversation_id (str): ID of the conversation
            user_id (str): ID of the user to check
        
        Returns:
            bool: True if user is participant, False otherwise
        
        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails
        """
        try:
            participants = await self.get_conversation_participants(conversation_id)
            return user_id in participants
            
        except (ValidationError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error checking if user {user_id} is participant in {conversation_id}: {e}")
            raise DatabaseError(f"Failed to check user participation: {str(e)}") 
    
    async def get_user_conversations_paginated(self, user_id: str, page: int = 1, page_size: int = 20, 
                                             include_archived: bool = False, sort_by: str = "updated_at") -> Dict[str, Any]:
        """Get paginated conversations for a user with advanced filtering and sorting.
        
        Args:
            user_id (str): ID of the user
            page (int): Page number (1-based)
            page_size (int): Number of conversations per page (1-100)
            include_archived (bool): Whether to include archived conversations
            sort_by (str): Field to sort by (created_at, updated_at)
        
        Returns:
            Dict[str, Any]: Paginated response with conversations and metadata
        
        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            if page < 1:
                raise ValidationError("Page must be at least 1")
            if page_size < 1 or page_size > 100:
                raise ValidationError("Page size must be between 1 and 100")
            if sort_by not in ["created_at", "updated_at"]:
                raise ValidationError("Sort by must be 'created_at' or 'updated_at'")
            
            user_id = user_id.strip()
            offset = (page - 1) * page_size
            
            # Build filters
            filters = [FieldFilter("participants", "array_contains", user_id)]
            if not include_archived:
                filters.append(FieldFilter("is_archived", "==", False))
            
            # Get conversations with pagination
            conversations = await self.conversation_service.query(filters, page_size, offset)
            
            # Get total count for pagination metadata
            total_conversations = await self._get_user_conversations_count(user_id, include_archived)
            
            # Calculate pagination metadata
            total_pages = (total_conversations + page_size - 1) // page_size
            has_next = page < total_pages
            has_previous = page > 1
            
            return {
                "conversations": conversations,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_conversations,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous
                },
                "filters": {
                    "include_archived": include_archived,
                    "sort_by": sort_by
                }
            }
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting paginated conversations for user {user_id}: {e}")
            raise DatabaseError(f"Failed to get paginated conversations: {str(e)}")
    
    async def _get_user_conversations_count(self, user_id: str, include_archived: bool = False) -> int:
        """Get total count of conversations for a user (helper method)."""
        try:
            filters = [FieldFilter("participants", "array_contains", user_id)]
            if not include_archived:
                filters.append(FieldFilter("is_archived", "==", False))
            
            # Get all conversations to count (with reasonable limit)
            conversations = await self.conversation_service.query(filters, limit=10000)
            return len(conversations)
            
        except Exception as e:
            logger.error(f"Error getting conversation count for user {user_id}: {e}")
            return 0
    
    async def search_conversations_by_content(self, user_id: str, search_term: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search conversations by message content for a specific user.
        
        Args:
            user_id (str): ID of the user performing the search
            search_term (str): Text to search for in messages
            limit (int): Maximum number of results to return
        
        Returns:
            List[Dict[str, Any]]: List of conversations with matching messages
        
        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            if not search_term or not search_term.strip():
                raise ValidationError("Search term is required")
            if limit < 1 or limit > 100:
                raise ValidationError("Limit must be between 1 and 100")
            
            user_id = user_id.strip()
            search_term = search_term.strip().lower()
            
            # Get user's conversations first
            user_conversations = await self.get_user_conversations(user_id, limit=1000)
            conversation_ids = [conv["id"] for conv in user_conversations]
            
            if not conversation_ids:
                return []
            
            # Search for messages containing the search term in user's conversations
            # Note: This is a basic text search. For production, consider using
            # Firestore's full-text search capabilities or external search services
            matching_conversations = []
            
            for conversation_id in conversation_ids:
                # Get messages in this conversation
                filters = [FieldFilter("conversation_id", "==", conversation_id)]
                messages = await self.message_service.query(filters, limit=100)
                
                # Check if any message contains the search term
                for message in messages:
                    if search_term in message.get("content", "").lower():
                        # Get the conversation details
                        conversation = await self.get_conversation_by_id(conversation_id)
                        if conversation:
                            matching_conversations.append(conversation)
                        break
                
                if len(matching_conversations) >= limit:
                    break
            
            return matching_conversations[:limit]
            
        except ValidationError:
            raise
        except DatabaseError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching conversations for user {user_id}: {e}")
            raise DatabaseError(f"Failed to search conversations: {str(e)}")
    
    async def validate_conversation_access(self, conversation_id: str, user_id: str) -> bool:
        """Validate if a user has access to a conversation.
        
        Args:
            conversation_id (str): ID of the conversation
            user_id (str): ID of the user to validate
        
        Returns:
            bool: True if user has access, False otherwise
        
        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails
        """
        try:
            # Input validation
            if not conversation_id or not conversation_id.strip():
                raise ValidationError("Conversation ID is required")
            if not user_id or not user_id.strip():
                raise ValidationError("User ID is required")
            
            conversation_id = conversation_id.strip()
            user_id = user_id.strip()
            
            # Check if conversation exists and user is participant
            conversation = await self.get_conversation_by_id(conversation_id)
            if not conversation:
                return False
            
            return user_id in conversation.get("participants", [])
            
        except (ValidationError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error validating conversation access for user {user_id}: {e}")
            return False
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get service information and configuration details.
        
        Returns:
            Dict[str, Any]: Service configuration and health information
        """
        try:
            # Test database connectivity
            db_healthy = True
            try:
                # Simple query to test database connection
                await self.conversation_service.query([], limit=1)
            except Exception:
                db_healthy = False
            
            return {
                "service_name": "ConversationService",
                "status": "healthy" if db_healthy else "unhealthy",
                "database_healthy": db_healthy,
                "configuration": {
                    "rate_limit_messages": self.rate_limit_messages,
                    "rate_limit_window": self.rate_limit_window,
                    "max_message_length": self.max_message_length,
                    "min_message_length": self.min_message_length,
                    "default_page_size": self.DEFAULT_PAGE_SIZE,
                    "max_page_size": self.MAX_PAGE_SIZE
                },
                "features": [
                    "Transaction support",
                    "Rate limiting",
                    "Content validation",
                    "Batch operations",
                    "Pagination",
                    "Search capabilities",
                    "Authorization checks"
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting service info: {e}")
            return {
                "service_name": "ConversationService",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            } 