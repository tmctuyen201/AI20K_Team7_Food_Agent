"""Session creation — uses JSON file store (Phase 1, no MongoDB)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, status
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
    users_store.set(user_id, {
        "user_id": user_id,
        "name": name or existing.get("name", ""),
        "latitude": latitude,
        "longitude": longitude,
    })

    # Create session
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    sessions_store.set(session_id, {
        "session_id": session_id,
        "user_id": user_id,
        "latitude": latitude,
        "longitude": longitude,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Mint JWT (24h)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    token = create_access_token(
        {"user_id": user_id, "session_id": session_id},
        expires_delta=timedelta(hours=24),
    )

    logger.info("session_created", session_id=session_id, user_id=user_id)
    return session_id, token, expires


@router.post("/api/session", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
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
    latitude: float = Query(default=21.0285, description="Latitude for session"),
    longitude: float = Query(default=105.8542, description="Longitude for session"),
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