"""History service — stubs for Phase 1 (no DB yet)."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("foodie.history")


async def save_selection(user_id: str, place: dict) -> None:
    """Save a restaurant selection for a user.

    Phase 1: log only (no DB persistence).
    """
    logger.info(
        "selection_saved",
        user_id=user_id,
        place_id=place.get("place_id"),
        name=place.get("name"),
    )


async def get_user_preference(user_id: str) -> dict | None:
    """Get user preference from DB.

    Phase 1: return None (no DB yet).
    """
    logger.info(
        "preference_fetched",
        user_id=user_id,
        found=False,
    )
    return None


async def save_session(session_id: str, state: dict) -> None:
    """Save session state to DB.

    Phase 1: log only.
    """
    logger.info(
        "session_saved",
        session_id=session_id,
    )


async def load_session(session_id: str) -> dict | None:
    """Load session state from DB.

    Phase 1: return None.
    """
    return None
