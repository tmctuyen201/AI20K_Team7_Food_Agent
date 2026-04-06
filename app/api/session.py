"""Session creation and JWT authentication endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import create_access_token
from app.db.models import LatLng, Session, User, UserPreference
from app.db.queries import create_session as _create_session, create_user as _create_user, get_user as _get_user
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("foodie.api.session")


class CreateSessionRequest(BaseModel):
    """Request payload for creating a new chat session."""

    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    name: str = Field(default="", description="Optional display name")
    latitude: float = Field(default=21.0285, ge=-90.0, le=90.0, description="Default latitude (Hanoi)")
    longitude: float = Field(default=105.8542, ge=-180.0, le=180.0, description="Default longitude (Hanoi)")


class CreateSessionResponse(BaseModel):
    """Response payload returned after session creation."""

    session_id: str
    user_id: str
    token: str
    expires_at: str


@router.post(
    "/api/session",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
    description="Creates (or retrieves) a user record, creates a new session, and returns a JWT token.",
)
async def create_new_session(request: CreateSessionRequest) -> CreateSessionResponse:
    """Create a new chat session and return a JWT access token.

    If the user_id already exists, the existing user record is reused.
    """
    # ── Resolve / create user ──────────────────────────────────────────────────
    existing_user = await _get_user(request.user_id)

    if existing_user is None:
        user = User(
            user_id=request.user_id,
            name=request.name,
            default_location=LatLng(lat=request.latitude, lng=request.longitude),
            preference=UserPreference(),
        )
        await _create_user(user)
        logger.info("user_auto_created", user_id=request.user_id)
    else:
        logger.info("user_reused", user_id=request.user_id)

    # ── Create session ─────────────────────────────────────────────────────────
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session = Session(
        session_id=session_id,
        user_id=request.user_id,
        location=LatLng(lat=request.latitude, lng=request.longitude),
    )
    await _create_session(session)
    logger.info("session_created", session_id=session_id, user_id=request.user_id)

    # ── Mint JWT ───────────────────────────────────────────────────────────────
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    token = create_access_token(
        {
            "user_id": request.user_id,
            "session_id": session_id,
        },
        expires_delta=timedelta(hours=24),
    )

    return CreateSessionResponse(
        session_id=session_id,
        user_id=request.user_id,
        token=token,
        expires_at=expires.isoformat(),
    )