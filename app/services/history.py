"""History service — Phase 1 uses JSON file store.

Replace with MongoDB in Phase 2 by updating these functions.
All functions are sync wrappers around the JSON store.
"""

from __future__ import annotations

from datetime import datetime

from app.agent.sub_agents.data_store import (
    add_favorite_cuisine as _add_fav,
    find_selection as _find_sel,
    get_user_preference as _get_pref,
    insert_selection as _insert_sel,
    list_selections as _list_sels,
    remove_favorite_cuisine as _remove_fav,
    update_selection as _update_sel,
    upsert_user_preference as _upsert_pref,
)
from app.core.logging import get_logger

logger = get_logger("foodie.history")


async def save_selection(user_id: str, place: dict) -> dict:
    """Save a restaurant selection for a user.

    If the place was already selected, updates the existing record.
    Also updates the user's favorite cuisines if cuisine_type is provided.

    Args:
        user_id: User identifier.
        place: Dict with place_id, name, cuisine_type, rating.

    Returns:
        Dict with success status and selection details.
    """
    place_id = place.get("place_id", "")
    name = place.get("name", "")
    cuisine_type = place.get("cuisine_type")
    rating = place.get("rating", 0.0)

    if not user_id or not place_id or not name:
        raise ValueError("user_id, place_id, and name are required")

    if not (0.0 <= rating <= 5.0):
        raise ValueError("rating must be between 0.0 and 5.0")

    now = datetime.utcnow().isoformat()
    selection_data = {
        "user_id": user_id,
        "place_id": place_id,
        "name": name,
        "cuisine_type": cuisine_type,
        "rating": rating,
        "selected_at": now,
    }

    existing = _find_sel(user_id, place_id)
    if existing:
        _update_sel(user_id, place_id, {
            "name": name,
            "cuisine_type": cuisine_type,
            "rating": rating,
            "selected_at": now,
        })
        logger.info(
            "selection_updated",
            user_id=user_id,
            place_id=place_id,
            name=name,
        )
        message = "Đã cập nhật lựa chọn!"
    else:
        _insert_sel(selection_data)
        logger.info(
            "selection_saved",
            user_id=user_id,
            place_id=place_id,
            name=name,
        )
        message = "Đã lưu vào lịch sử!"

    preference_updated = False
    if cuisine_type:
        try:
            _add_favorite_cuisine(user_id, cuisine_type)
            preference_updated = True
            logger.info(
                "preference_updated",
                user_id=user_id,
                cuisine=cuisine_type,
            )
        except Exception as e:
            logger.warning(
                "preference_update_failed",
                user_id=user_id,
                cuisine=cuisine_type,
                error=str(e),
            )

    return {
        "success": True,
        "message": message,
        "selection_id": place_id,
        "preference_updated": preference_updated,
    }


async def get_user_preference(user_id: str) -> dict:
    """Get user preference from JSON store.

    Returns empty preference structure if user not found.
    """
    pref = _get_pref(user_id)
    selections = _list_sels(user_id, limit=1000)
    total = len(selections)
    logger.info(
        "preference_fetched",
        user_id=user_id,
        found=total > 0,
        total_selections=total,
    )
    return pref


async def add_favorite_cuisine(user_id: str, cuisine: str) -> dict:
    """Add a cuisine to user's favorite list."""
    _add_fav(user_id, cuisine)
    logger.info("favorite_cuisine_added", user_id=user_id, cuisine=cuisine)
    return {"success": True, "cuisine": cuisine}


async def remove_favorite_cuisine(user_id: str, cuisine: str) -> dict:
    """Remove a cuisine from user's favorite list."""
    _remove_fav(user_id, cuisine)
    logger.info("favorite_cuisine_removed", user_id=user_id, cuisine=cuisine)
    return {"success": True, "cuisine": cuisine}


async def get_user_selections(
    user_id: str,
    limit: int = 20,
    skip: int = 0,
) -> list[dict]:
    """Get user's selection history, most recent first."""
    sels = _list_sels(user_id, limit=limit, skip=skip)
    logger.info(
        "selections_fetched",
        user_id=user_id,
        count=len(sels),
    )
    return sels


async def check_selection_exists(user_id: str, place_id: str) -> bool:
    """Check if user has already selected this place."""
    return _find_sel(user_id, place_id) is not None


async def save_session(session_id: str, state: dict) -> None:
    """Save session state.

    Phase 1: log only.
    """
    logger.info(
        "session_saved",
        session_id=session_id,
        keys=list(state.keys()),
    )


async def load_session(session_id: str) -> dict | None:
    """Load session state.

    Phase 1: not implemented (return None).
    """
    return None
