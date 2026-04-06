"""JSON file-based query helpers — no MongoDB required."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.db.connection import users_store, sessions_store, selections_store
from app.db.models import Session, Selection, User, UserPreference


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


async def get_user(user_id: str) -> Optional[User]:
    """Retrieve a user by user_id, or None if not found."""
    data = users_store.get(user_id)
    return User(**data) if data else None


async def create_user(user: User) -> bool:
    """Insert a new user document. Returns True on success."""
    try:
        users_store.set(user.user_id, user.model_dump())
        return True
    except Exception:
        return False


async def upsert_user(user_id: str, name: str = "", lat: float = 0.0, lng: float = 0.0, city: str = "") -> None:
    """Insert or replace a user document."""
    users_store.set(user_id, {
        "user_id": user_id,
        "name": name,
        "default_location": {"lat": lat, "lng": lng},
        "city": city,
    })


async def get_user_preference(user_id: str) -> UserPreference:
    """Return the user's preference sub-document."""
    data = users_store.get(user_id)
    if data and "preference" in data:
        return UserPreference(**data["preference"])
    return UserPreference()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


async def get_session(session_id: str) -> Optional[Session]:
    """Retrieve a session by session_id."""
    data = sessions_store.get(session_id)
    return Session(**data) if data else None


async def create_session(session: Session) -> bool:
    """Insert a new session document."""
    try:
        sessions_store.set(session.session_id, session.model_dump())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


async def save_selection(selection: Selection, update_preference: bool = True) -> bool:
    """Insert a restaurant selection. Optionally update the user's cuisine preference."""
    try:
        # Use user_id + place_id as composite key
        key = f"{selection.user_id}:{selection.place_id}"
        selections_store.set(key, selection.model_dump())

        if update_preference and selection.cuisine_type:
            user_data = users_store.get(selection.user_id) or {}
            prefs = user_data.get("preference", {})
            fav_cuisines = prefs.get("favorite_cuisines", [])
            if selection.cuisine_type not in fav_cuisines:
                fav_cuisines.append(selection.cuisine_type)
            prefs["favorite_cuisines"] = fav_cuisines
            user_data["preference"] = prefs
            users_store.set(selection.user_id, user_data)

        return True
    except Exception:
        return False


async def get_user_selections(
    user_id: str,
    limit: int = 20,
    skip: int = 0,
) -> list[Selection]:
    """Return the most recent selections for a user."""
    all_selections = []
    for key, data in selections_store.items():
        if data.get("user_id") == user_id:
            all_selections.append(data)

    # Sort by selected_at descending
    all_selections.sort(key=lambda x: x.get("selected_at", ""), reverse=True)

    # Apply pagination
    return [Selection(**s) for s in all_selections[skip : skip + limit]]


async def get_selection_count(user_id: str) -> int:
    """Return the total number of selections for a user."""
    return sum(1 for _, data in selections_store.items() if data.get("user_id") == user_id)


async def get_top_cuisines(user_id: str, limit: int = 5) -> list[dict]:
    """Return the user's most-frequently selected cuisines."""
    cuisine_counts: dict[str, int] = {}
    for _, data in selections_store.items():
        if data.get("user_id") == user_id:
            cuisine = data.get("cuisine_type") or "unknown"
            cuisine_counts[cuisine] = cuisine_counts.get(cuisine, 0) + 1

    # Sort by count descending
    sorted_cuisines = sorted(cuisine_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"cuisine": c, "count": n} for c, n in sorted_cuisines[:limit]]
