import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.services.conversation_service import ConversationService
from app.api.exceptions import ValidationError, ResourceNotFoundError


class TestConversationService:
    """Test cases for ConversationService"""
    
    @pytest.mark.asyncio
    async def test_create_conversation(self, mock_conversation_service):
        """Test creating conversation"""
        conversation_data = {
            "participants": ["user1", "user2"],
            "conversation_type": "direct",
            "title": "Test Conversation"
        }
        
        result = await mock_conversation_service.create_conversation("user1", conversation_data)
        
        assert result is not None
        mock_conversation_service.database_service.create_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message(self, mock_conversation_service):
        """Test sending message"""
        message_data = {
            "content": "Hello, how are you?",
            "message_type": "text"
        }
        
        result = await mock_conversation_service.send_message(
            "conversation123", "user123", message_data
        )
        
        assert result is not None
        mock_conversation_service.database_service.create_document.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_messages(self, mock_conversation_service):
        """Test getting messages"""
        mock_conversation_service.database_service.query_documents.return_value = [
            {"id": "msg1", "content": "Hello", "sender_id": "user1"},
            {"id": "msg2", "content": "Hi there", "sender_id": "user2"}
        ]
        mock_conversation_service.database_service.count_documents.return_value = 2
        
        result = await mock_conversation_service.get_messages(
            "conversation123", "user123", page=1, limit=10
        )
        
        assert len(result["messages"]) == 2
        assert result["total"] == 2 