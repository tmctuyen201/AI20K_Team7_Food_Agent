"""WebSocket endpoint for real-time chat with streaming response."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.agent.runner import AgentRunner
from app.core.auth import verify_token
from app.db.models import ScoredPlace

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self.active_connections.pop(session_id, None)

    async def send_token(self, session_id: str, token: str) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json({
                "type": "token",
                "data": token,
            })

    async def send_done(self, session_id: str, places: list[ScoredPlace]) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json({
                "type": "done",
                "data": {"places": [p.model_dump() for p in places]},
            })

    async def send_error(self, session_id: str, message: str) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json({
                "type": "error",
                "message": message,
            })


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = Query(...)) -> None:
    """WebSocket endpoint for chat with streaming response.

    Query parameters:
        token: JWT access token containing user_id and session_id.

    Message protocol (client → server):
        {"text": "I want Italian food near me"}

    Message protocol (server → client):
        {"type": "token", "data": "..."}     — streaming token chunk
        {"type": "done",  "data": {"places": [...]}}  — final response + places
        {"type": "error", "message": "..."}  — error occurred
    """
    session_id = ""
    try:
        # Verify token and extract payload
        payload = verify_token(token)
        user_id = str(payload.get("user_id", ""))
        session_id = str(payload.get("session_id", ""))

        if not user_id or not session_id:
            await websocket.send_json({"type": "error", "message": "Invalid token payload"})
            return

        await manager.connect(websocket, session_id)

        agent_runner = AgentRunner(user_id=user_id, session_id=session_id)

        while True:
            # Receive message from client
            raw = await websocket.receive_text()
            message = json.loads(raw)
            user_text = str(message.get("text", "")).strip()

            if not user_text:
                continue

            # Stream response token by token (use async run_async)
            async for token_text in agent_runner.run_async(user_text):
                await manager.send_token(session_id, token_text)

            # Send final payload with ranked places
            final_places = agent_runner.get_final_places()
            await manager.send_done(session_id, final_places)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except json.JSONDecodeError:
        if session_id:
            await manager.send_error(session_id, "Invalid JSON message")
    except Exception as e:
        if session_id:
            await manager.send_error(session_id, str(e))
        manager.disconnect(session_id)