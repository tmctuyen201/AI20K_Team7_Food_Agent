"""Mock data loaded from users.json (Phase 1 — no real GPS)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("foodie.mock_data")

_USERS_JSON = Path(__file__).parent / "users.json"


def _load_users() -> list[dict]:
    """Load and flatten users from JSON file."""
    try:
        data = json.loads(_USERS_JSON.read_text(encoding="utf-8"))
        users = []
        for u in data["mock_users"]:
            loc = u["location"]
            # Flatten nested location into top-level fields
            # address is used as the display label (replaces old "city")
            users.append({
                "user_id": u["user_id"],
                "name": u["name"],
                "lat": loc["lat"],
                "lng": loc["lng"],
                "address": loc["address"],
            })
        logger.info("mock_users_loaded", count=len(users))
        return users
    except FileNotFoundError:
        logger.error("mock_users_file_not_found", path=str(_USERS_JSON))
        raise
    except (KeyError, ValueError) as e:
        logger.error("mock_users_invalid_schema", error=str(e))
        raise


MOCK_USERS: list[dict] = _load_users()


def get_mock_location(user_id: str) -> dict:
    """Return flattened location dict for a known user_id, or fallback to first user."""
    for user in MOCK_USERS:
        if user["user_id"] == user_id:
            return user

    logger.warning("mock_location_fallback", user_id=user_id, fallback=MOCK_USERS[0]["user_id"])
    return MOCK_USERS[0]
