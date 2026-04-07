"""Session creation — uses JSON file store (Phase 1, no MongoDB)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import create_access_token
from app.core.logging import get_logger
from app.db.connection import users_store, sessions_store

router = APIRouter()
logger = get_logger("foodie.api.session")


class CreateSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(default="")
    latitude: float = Field(default=21.0285)
    longitude: float = Field(default=105.8542)


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    token: str
    expires_at: str


def _create_session_sync(
    user_id: str,
    name: str = "",
    latitude: float = 21.0285,
    longitude: float = 105.8542,
) -> tuple[str, str, datetime]:
    """Create session + JWT synchronously (shared by both POST and GET)."""
    # Upsert user in JSON store
    existing = users_store.get(user_id) or {}
    users_store.set(
        user_id,
        {
            "user_id": user_id,
            "name": name or existing.get("name", ""),
            "latitude": latitude,
            "longitude": longitude,
        },
    )

    # Create session
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    sessions_store.set(
        session_id,
        {
            "session_id": session_id,
            "user_id": user_id,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Also initialize chat history for this session
    from app.db.connection import chat_history_store

    all_chat_sessions = chat_history_store._read()
    if session_id not in all_chat_sessions:
        all_chat_sessions[session_id] = {"messages": []}
        chat_history_store._write(all_chat_sessions)

    # Mint JWT (24h)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    token = create_access_token(
        {"user_id": user_id, "session_id": session_id},
        expires_delta=timedelta(hours=24),
    )

    logger.info("session_created", session_id=session_id, user_id=user_id)
    return session_id, token, expires


@router.post(
    "/api/session",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
    session_id, token, expires = _create_session_sync(
        user_id=request.user_id,
        name=request.name,
        latitude=request.latitude,
        longitude=request.longitude,
    )

    return CreateSessionResponse(
        session_id=session_id,
        user_id=request.user_id,
        token=token,
        expires_at=expires.isoformat(),
    )


@router.get("/api/session", response_model=CreateSessionResponse)
async def get_or_create_session(
    user_id: str = Query(..., min_length=1, description="User identifier"),
    name: str = Query(default="", description="User display name"),
    latitude: float = Query(
        default=21.0285, description="Latitude for session"),
    longitude: float = Query(
        default=105.8542, description="Longitude for session"),
) -> CreateSessionResponse:
    """Auto-create a session for a user on first website access.

    This endpoint ensures the user always has a valid session token before
    connecting to WebSocket, avoiding "missing session" errors on first load.

    Query params:
        user_id: Required user identifier (can be anonymous like "anon_xxx")
        name: Optional display name
        latitude: Session latitude (default: Hà Nội)
        longitude: Session longitude (default: Hà Nội)

    Returns:
        JSON with session_id, user_id, token, expires_at

    Example frontend call on page load:
        GET /api/session?user_id=anon_abc123&name=Guest
    """
    session_id, token, expires = _create_session_sync(
        user_id=user_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
    )

    return CreateSessionResponse(
        session_id=session_id,
        user_id=user_id,
        token=token,
        expires_at=expires.isoformat(),
    )


class ChatMessage(BaseModel):
    timestamp: str
    role: str  # "user" or "assistant"
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


@router.get("/api/sessions/{user_id}")
async def get_user_sessions(user_id: str) -> list[dict]:
    """Return all sessions for a user, most recent first."""
    all_sessions = sessions_store._read()

    user_sessions = [
        {
            "session_id": sid,
            "user_id": data.get("user_id", ""),
            "created_at": data.get("created_at", ""),
        }
        for sid, data in all_sessions.items()
        if data.get("user_id") == user_id
    ]

    user_sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    logger.info("sessions_listed", user_id=user_id, count=len(user_sessions))
    return user_sessions


@router.get("/api/session/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str) -> ChatHistoryResponse:
    """Get chat history for a session from the JSON store."""
    from app.db.connection import chat_history_store

    # Load all messages for this session
    all_sessions = chat_history_store._read()
    session_messages = all_sessions.get(session_id, {}).get("messages", [])

    messages = [
        ChatMessage(
            timestamp=msg.get("timestamp", ""),
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
        )
        for msg in session_messages
        if msg.get("content")
    ]

    logger.info(
        "chat_history_retrieved", session_id=session_id, message_count=len(messages)
    )

    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages,
    )
