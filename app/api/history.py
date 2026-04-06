"""History endpoints for selection tracking and user preferences."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import verify_token
from app.db.models import Selection
from app.db.queries import (
    get_selection_count,
    get_top_cuisines,
    get_user_selections,
    save_selection,
)
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("foodie.api.history")


# ── Request / response models ───────────────────────────────────────────────────


class SelectionRequest(BaseModel):
    """Payload for saving a restaurant selection."""

    user_id: str = Field(..., min_length=1)
    place_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    cuisine_type: Optional[str] = None
    rating: float = Field(default=0.0, ge=0.0, le=5.0)


class HistoryResponse(BaseModel):
    """Response for the history endpoint."""

    selections: list[dict]
    total: int
    top_cuisines: list[dict]


class SelectionResponse(BaseModel):
    """Response for the selection save endpoint."""

    success: bool
    message: str


# ── Routes ──────────────────────────────────────────────────────────────────────


@router.get(
    "/api/history/{user_id}",
    response_model=HistoryResponse,
    summary="Get user's selection history",
    description="Returns the user's restaurant selection history, total count, and top cuisines.",
)
async def get_history(
    user_id: str,
    limit: int = Field(default=20, ge=1, le=100),
    skip: int = Field(default=0, ge=0),
) -> HistoryResponse:
    """Fetch a user's restaurant selection history.

    Args:
        user_id: Target user identifier.
        limit: Maximum number of records to return (default 20).
        skip: Number of records to skip for pagination (default 0).
    """
    selections = await get_user_selections(user_id, limit=limit, skip=skip)
    total = await get_selection_count(user_id)
    top_cuisines = await get_top_cuisines(user_id, limit=5)

    logger.info(
        "history_fetched",
        user_id=user_id,
        returned=len(selections),
        total=total,
    )

    return HistoryResponse(
        selections=[s.model_dump(mode="json") for s in selections],
        total=total,
        top_cuisines=top_cuisines,
    )


@router.post(
    "/api/selection",
    response_model=SelectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a restaurant selection",
    description="Records a user's restaurant choice and updates their cuisine preference.",
)
async def create_selection(request: SelectionRequest) -> SelectionResponse:
    """Save (or update) a restaurant selection for a user.

    Args:
        request: Selection details including place_id, name, cuisine_type, and rating.
    """
    selection = Selection(
        user_id=request.user_id,
        place_id=request.place_id,
        name=request.name,
        cuisine_type=request.cuisine_type,
        rating=request.rating,
    )

    success = await save_selection(selection, update_preference=True)

    message = "Selection saved" if success else "Failed to save"
    status_code = status.HTTP_201_CREATED if success else status.HTTP_500_INTERNAL_SERVER_ERROR

    if not success:
        logger.error("selection_save_failed", user_id=request.user_id, place_id=request.place_id)
    else:
        logger.info("selection_saved", user_id=request.user_id, place_id=request.place_id)

    return SelectionResponse(success=success, message=message)