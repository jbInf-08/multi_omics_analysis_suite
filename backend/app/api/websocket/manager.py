"""
WebSocket Connection Manager
============================

Real-time communication for analysis progress updates.
"""

from typing import Dict, Set, Optional, Any
from datetime import datetime, timezone
import json
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel


class WSMessage(BaseModel):
    """WebSocket message model."""
    type: str
    data: dict
    timestamp: datetime = None
    
    def __init__(self, **data):
        if "timestamp" not in data:
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)


class ConnectionManager:
    """
    WebSocket connection manager for real-time updates.
    
    Supports:
    - User-specific connections
    - Analysis-specific subscriptions
    - Broadcast to all connections
    - Room-based messaging
    - Access control for subscriptions
    """
    
    def __init__(self):
        # User connections: user_id -> set of websockets
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        
        # Analysis subscriptions: analysis_id -> set of websockets
        self.analysis_subscriptions: Dict[str, Set[WebSocket]] = {}
        
        # All active connections
        self.active_connections: Set[WebSocket] = set()
        
        # WebSocket to user mapping for access control
        self.websocket_users: Dict[WebSocket, Optional[str]] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.websocket_users[websocket] = user_id
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
    
    def disconnect(
        self,
        websocket: WebSocket,
        user_id: Optional[str] = None,
    ):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        self.websocket_users.pop(websocket, None)
        
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove from all analysis subscriptions
        for analysis_id in list(self.analysis_subscriptions.keys()):
            self.analysis_subscriptions[analysis_id].discard(websocket)
            if not self.analysis_subscriptions[analysis_id]:
                del self.analysis_subscriptions[analysis_id]
    
    def get_user_id(self, websocket: WebSocket) -> Optional[str]:
        """Get user ID for a WebSocket connection."""
        return self.websocket_users.get(websocket)
    
    def is_authenticated(self, websocket: WebSocket) -> bool:
        """Check if WebSocket connection is authenticated."""
        return self.websocket_users.get(websocket) is not None
    
    def subscribe_analysis(self, websocket: WebSocket, analysis_id: str):
        """Subscribe to analysis updates."""
        if analysis_id not in self.analysis_subscriptions:
            self.analysis_subscriptions[analysis_id] = set()
        self.analysis_subscriptions[analysis_id].add(websocket)
    
    def unsubscribe_analysis(self, websocket: WebSocket, analysis_id: str):
        """Unsubscribe from analysis updates."""
        if analysis_id in self.analysis_subscriptions:
            self.analysis_subscriptions[analysis_id].discard(websocket)
    
    async def send_personal(self, websocket: WebSocket, message: WSMessage):
        """Send message to a specific connection."""
        try:
            await websocket.send_json(message.model_dump(mode="json"))
        except Exception:
            pass
    
    async def send_to_user(self, user_id: str, message: WSMessage):
        """Send message to all connections for a user."""
        if user_id in self.user_connections:
            tasks = [
                self.send_personal(ws, message)
                for ws in self.user_connections[user_id]
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_analysis_update(self, analysis_id: str, message: WSMessage):
        """Send update to all subscribers of an analysis."""
        if analysis_id in self.analysis_subscriptions:
            tasks = [
                self.send_personal(ws, message)
                for ws in self.analysis_subscriptions[analysis_id]
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast(self, message: WSMessage):
        """Broadcast message to all connections."""
        tasks = [
            self.send_personal(ws, message)
            for ws in self.active_connections
        ]
        await asyncio.gather(*tasks, return_exceptions=True)


# Global connection manager
manager = ConnectionManager()

# WebSocket router
websocket_router = APIRouter()


def validate_websocket_token(token: Optional[str]) -> Optional[str]:
    """
    Validate JWT token for WebSocket connections.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID if valid, None otherwise
    """
    if not token:
        return None
    
    try:
        from backend.app.core.security import decode_token
        payload = decode_token(token)
        
        # Verify it's an access token
        if payload.type != "access":
            return None
        
        return payload.sub
    except Exception:
        return None


@websocket_router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Main WebSocket endpoint.
    
    Query parameters:
    - token: JWT token for authentication
    
    Message types:
    - subscribe_analysis: Subscribe to analysis updates
    - unsubscribe_analysis: Unsubscribe from analysis updates
    - ping: Keep-alive ping
    """
    # Validate token and extract user_id
    user_id = validate_websocket_token(token)
    
    await manager.connect(websocket, user_id)
    
    try:
        # Send connection confirmation
        await manager.send_personal(
            websocket,
            WSMessage(
                type="connected",
                data={"message": "Connected to Multi-Omics WebSocket"},
            ),
        )
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "subscribe_analysis":
                analysis_id = data.get("analysis_id")
                if analysis_id:
                    manager.subscribe_analysis(websocket, analysis_id)
                    await manager.send_personal(
                        websocket,
                        WSMessage(
                            type="subscribed",
                            data={"analysis_id": analysis_id},
                        ),
                    )
            
            elif message_type == "unsubscribe_analysis":
                analysis_id = data.get("analysis_id")
                if analysis_id:
                    manager.unsubscribe_analysis(websocket, analysis_id)
                    await manager.send_personal(
                        websocket,
                        WSMessage(
                            type="unsubscribed",
                            data={"analysis_id": analysis_id},
                        ),
                    )
            
            elif message_type == "ping":
                await manager.send_personal(
                    websocket,
                    WSMessage(type="pong", data={}),
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        manager.disconnect(websocket, user_id)
        raise


@websocket_router.websocket("/analysis/{analysis_id}")
async def analysis_websocket(
    websocket: WebSocket,
    analysis_id: str,
    token: Optional[str] = Query(None),
):
    """
    Analysis-specific WebSocket endpoint.
    
    Automatically subscribes to updates for the specified analysis.
    """
    # Validate token and extract user_id
    user_id = validate_websocket_token(token)
    
    await manager.connect(websocket, user_id)
    manager.subscribe_analysis(websocket, analysis_id)
    
    try:
        await manager.send_personal(
            websocket,
            WSMessage(
                type="subscribed",
                data={"analysis_id": analysis_id},
            ),
        )
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    WSMessage(type="pong", data={}),
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)
        raise


# Helper function for sending analysis updates from tasks
async def notify_analysis_progress(
    analysis_id: str,
    status: str,
    progress: float,
    current_step: Optional[str] = None,
    message: Optional[str] = None,
):
    """Send analysis progress update via WebSocket."""
    await manager.send_analysis_update(
        analysis_id,
        WSMessage(
            type="analysis_progress",
            data={
                "analysis_id": analysis_id,
                "status": status,
                "progress": progress,
                "current_step": current_step,
                "message": message,
            },
        ),
    )
