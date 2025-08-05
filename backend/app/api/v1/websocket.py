"""
WebSocket API endpoints for Athletes Networking App

This module provides WebSocket endpoints for real-time messaging and notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from typing import Dict, List, Optional
import json
import logging
from datetime import datetime

from app.api.dependencies import get_current_user_ws
from app.services.websocket_service import WebSocketService
from app.services.conversation_service import ConversationService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)

# Initialize services
websocket_service = WebSocketService()
conversation_service = ConversationService()
notification_service = NotificationService()

# Store active connections
active_connections: Dict[str, WebSocket] = {}

@router.websocket("/messages")
async def websocket_messages(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time messaging
    Connection: ws://api/v1/ws/messages?token=<jwt-token>
    """
    try:
        # Authenticate user
        user = await get_current_user_ws(token)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # Accept connection
        await websocket.accept()
        user_id = user["uid"]
        active_connections[user_id] = websocket
        
        logger.info(f"WebSocket connection established for user {user_id}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {"user_id": user_id},
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Notify other users that this user is online
        await websocket_service.broadcast_user_status(
            user_id=user_id,
            status="online",
            exclude_user_id=user_id
        )
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle different message types
                await handle_websocket_message(user_id, message_data, websocket)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket connection closed for user {user_id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user_id}: {str(e)}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Internal server error"},
                "timestamp": datetime.utcnow().isoformat()
            }))
        finally:
            # Clean up connection
            if user_id in active_connections:
                del active_connections[user_id]
            
            # Notify other users that this user is offline
            await websocket_service.broadcast_user_status(
                user_id=user_id,
                status="offline",
                exclude_user_id=user_id
            )
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
        if websocket.client_state.value < 3:  # Not closed
            await websocket.close(code=4000, reason="Internal server error")

async def handle_websocket_message(user_id: str, message_data: dict, websocket: WebSocket):
    """
    Handle incoming WebSocket messages
    """
    message_type = message_data.get("type")
    
    if message_type == "ping":
        # Handle heartbeat
        await websocket.send_text(json.dumps({
            "type": "pong",
            "data": {},
            "timestamp": datetime.utcnow().isoformat()
        }))
        
    elif message_type == "typing":
        # Handle typing indicator
        conversation_id = message_data.get("data", {}).get("conversation_id")
        is_typing = message_data.get("data", {}).get("is_typing", False)
        
        if conversation_id:
            await websocket_service.broadcast_typing_indicator(
                conversation_id=conversation_id,
                user_id=user_id,
                is_typing=is_typing,
                exclude_user_id=user_id
            )
    
    elif message_type == "message_read":
        # Handle message read status
        message_id = message_data.get("data", {}).get("message_id")
        
        if message_id:
            await conversation_service.mark_message_read(
                message_id=message_id,
                user_id=user_id
            )
            
            # Broadcast read status to other participants
            await websocket_service.broadcast_message_read(
                message_id=message_id,
                user_id=user_id
            )
    
    elif message_type == "send_message":
        # Handle sending a new message
        conversation_id = message_data.get("data", {}).get("conversation_id")
        content = message_data.get("data", {}).get("content")
        
        if conversation_id and content:
            # Save message to database
            message = await conversation_service.send_message(
                conversation_id=conversation_id,
                sender_id=user_id,
                content=content
            )
            
            # Broadcast message to other participants
            await websocket_service.broadcast_new_message(
                conversation_id=conversation_id,
                message=message,
                exclude_user_id=user_id
            )
    
    else:
        # Unknown message type
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": f"Unknown message type: {message_type}"},
            "timestamp": datetime.utcnow().isoformat()
        }))

@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time notifications
    Connection: ws://api/v1/ws/notifications?token=<jwt-token>
    """
    try:
        # Authenticate user
        user = await get_current_user_ws(token)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # Accept connection
        await websocket.accept()
        user_id = user["uid"]
        
        logger.info(f"Notification WebSocket connection established for user {user_id}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {"user_id": user_id},
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        try:
            while True:
                # Keep connection alive and wait for notifications
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "data": {},
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                    
        except WebSocketDisconnect:
            logger.info(f"Notification WebSocket connection closed for user {user_id}")
        except Exception as e:
            logger.error(f"Notification WebSocket error for user {user_id}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Notification WebSocket connection error: {str(e)}")
        if websocket.client_state.value < 3:  # Not closed
            await websocket.close(code=4000, reason="Internal server error")

# Helper functions for broadcasting messages
async def broadcast_to_user(user_id: str, message: dict):
    """
    Send message to specific user if they are connected
    """
    if user_id in active_connections:
        try:
            await active_connections[user_id].send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {str(e)}")
            # Remove disconnected user
            del active_connections[user_id]

async def broadcast_to_users(user_ids: List[str], message: dict, exclude_user_id: Optional[str] = None):
    """
    Send message to multiple users
    """
    for user_id in user_ids:
        if user_id != exclude_user_id:
            await broadcast_to_user(user_id, message) 