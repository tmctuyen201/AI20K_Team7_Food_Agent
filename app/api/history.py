"""History endpoints — uses JSON file store (Phase 1, no MongoDB)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.db.connection import users_store, selections_store

router = APIRouter()
logger = get_logger("foodie.api.history")


class SelectionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    place_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    cuisine_type: str | None = None
    rating: float = Field(default=0.0, ge=0.0, le=5.0)


class SelectionResponse(BaseModel):
    success: bool
    message: str


@router.get("/api/history/{user_id}")
async def get_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    # Get all selections for user
    selections = []
    for key, data in selections_store.items():
        if data.get("user_id") == user_id:
            selections.append(data)

    # Sort by selected_at descending
    selections.sort(key=lambda x: x.get("selected_at", ""), reverse=True)

    # Apply limit
    selections = selections[:limit]
    total = sum(1 for k, v in selections_store.items() if v.get("user_id") == user_id)

    # Count top cuisines
    cuisine_count: dict[str, int] = {}
    for sel in selections:
        cuisine = sel.get("cuisine_type") or "unknown"
        cuisine_count[cuisine] = cuisine_count.get(cuisine, 0) + 1

    top_cuisines = [
        {"cuisine": c, "count": cnt, "avg_rating": 0.0}
        for c, cnt in sorted(cuisine_count.items(), key=lambda x: -x[1])[:5]
    ]

    logger.info("history_fetched", user_id=user_id, returned=len(selections), total=total)

    return {
        "selections": selections,
        "total": total,
        "top_cuisines": top_cuisines,
    }


@router.post("/api/selection", response_model=SelectionResponse, status_code=status.HTTP_201_CREATED)
async def save_selection(request: SelectionRequest) -> SelectionResponse:
    now = datetime.utcnow().isoformat()
    selection_key = f"{request.user_id}:{request.place_id}"

    selection_data = {
        "user_id": request.user_id,
        "place_id": request.place_id,
        "name": request.name,
        "cuisine_type": request.cuisine_type,
        "rating": request.rating,
        "selected_at": now,
    }

    existing = selections_store.get(selection_key)
    if existing:
        # Update existing
        selections_store.set(selection_key, {**existing, **selection_data})
        logger.info("selection_updated", user_id=request.user_id, place_id=request.place_id)
    else:
        # Insert new
        selections_store.set(selection_key, selection_data)
        logger.info("selection_saved", user_id=request.user_id, place_id=request.place_id)

    # Update user's favorite cuisines
    if request.cuisine_type:
        user_data = users_store.get(request.user_id) or {}
        prefs = user_data.get("preference", {})
        fav_cuisines = prefs.get("favorite_cuisines", [])
        if request.cuisine_type not in fav_cuisines:
            fav_cuisines.append(request.cuisine_type)
        prefs["favorite_cuisines"] = fav_cuisines
        user_data["preference"] = prefs
        users_store.set(request.user_id, user_data)

    return SelectionResponse(success=True, message="Selection saved")
