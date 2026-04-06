"""Database query layer (Phase 1 — JSON file store).

All functions here are async wrappers around the synchronous JSON store.
Replace the underlying store with MongoDB in Phase 2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.models import Selection, Session, User
from app.db.connection import get_db_path
from app.core.logging import get_logger

logger = get_logger("foodie.db.queries")

if TYPE_CHECKING:
    from pathlib import Path


# ── JSON helpers ────────────────────────────────────────────────────────────────

import json


def _read_store(filename: str) -> dict:
    path = get_db_path(filename)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_store(filename: str, data: dict) -> None:
    path = get_db_path(filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


# ── User queries ────────────────────────────────────────────────────────────────

async def get_user(user_id: str) -> User | None:
    """Return a user by ID, or None if not found."""
    store = _read_store("users.json")
    raw = store.get(user_id)
    if raw is None:
        return None
    return User(**raw)


async def create_user(user: User) -> User:
    """Insert a new user into the store."""
    store = _read_store("users.json")
    store[user.user_id] = user.model_dump()
    _write_store("users.json", store)
    logger.info("user_created", user_id=user.user_id)
    return user


async def update_user(user_id: str, updates: dict) -> User | None:
    """Update user fields, return updated User or None if not found."""
    store = _read_store("users.json")
    if user_id not in store:
        return None
    store[user_id].update(updates)
    _write_store("users.json", store)
    return User(**store[user_id])


# ── Session queries ─────────────────────────────────────────────────────────────

async def get_session(session_id: str) -> Session | None:
    """Return a session by ID, or None if not found."""
    store = _read_store("sessions.json")
    raw = store.get(session_id)
    if raw is None:
        return None
    return Session(**raw)


async def create_session(session: Session) -> Session:
    """Insert a new session."""
    store = _read_store("sessions.json")
    store[session.session_id] = session.model_dump()
    _write_store("sessions.json", store)
    logger.info("session_created", session_id=session.session_id, user_id=session.user_id)
    return session


async def update_session(session_id: str, updates: dict) -> Session | None:
    """Update session fields."""
    store = _read_store("sessions.json")
    if session_id not in store:
        return None
    store[session_id].update(updates)
    _write_store("sessions.json", store)
    return Session(**store[session_id])


# ── Selection queries ───────────────────────────────────────────────────────────

async def get_selection(user_id: str, place_id: str) -> Selection | None:
    """Return a specific selection, or None."""
    store = _read_store("selections.json")
    for sel in store.get("selections", []):
        if sel.get("user_id") == user_id and sel.get("place_id") == place_id:
            return Selection(**sel)
    return None


async def get_user_selections(user_id: str, limit: int = 20, skip: int = 0) -> list[Selection]:
    """Return a user's selection history, newest first."""
    store = _read_store("selections.json")
    user_sels = [
        Selection(**s)
        for s in store.get("selections", [])
        if s.get("user_id") == user_id
    ]
    user_sels.sort(key=lambda s: s.selected_at, reverse=True)
    return user_sels[skip : skip + limit]


async def get_selection_count(user_id: str) -> int:
    """Return total number of selections for a user."""
    store = _read_store("selections.json")
    return sum(1 for s in store.get("selections", []) if s.get("user_id") == user_id)


async def save_selection(
    selection: Selection,
    update_preference: bool = False,
) -> bool:
    """Insert or update a selection. Optionally update user cuisine preference."""
    store = _read_store("selections.json")
    store.setdefault("selections", [])

    # Check for existing
    for i, sel in enumerate(store["selections"]):
        if sel.get("user_id") == selection.user_id and sel.get("place_id") == selection.place_id:
            store["selections"][i].update(selection.model_dump())
            _write_store("selections.json", store)
            logger.info("selection_updated", user_id=selection.user_id, place_id=selection.place_id)
            return True

    # New selection
    store["selections"].append(selection.model_dump())
    _write_store("selections.json", store)
    logger.info("selection_saved", user_id=selection.user_id, place_id=selection.place_id)

    # Update cuisine preference
    if update_preference and selection.cuisine_type:
        await _add_favorite_cuisine(selection.user_id, selection.cuisine_type)

    return True


async def _add_favorite_cuisine(user_id: str, cuisine: str) -> None:
    """Add a cuisine to the user's favorite list."""
    store = _read_store("users.json")
    if user_id not in store:
        return
    favs = store[user_id].setdefault("preference", {}).setdefault("favorite_cuisines", [])
    if cuisine not in favs:
        favs.append(cuisine)
    _write_store("users.json", store)


async def get_top_cuisines(user_id: str, limit: int = 5) -> list[dict]:
    """Return the most frequently selected cuisines for a user."""
    store = _read_store("selections.json")
    counts: dict[str, int] = {}
    for sel in store.get("selections", []):
        if sel.get("user_id") == user_id and sel.get("cuisine_type"):
            cuisine = sel["cuisine_type"]
            counts[cuisine] = counts.get(cuisine, 0) + 1
    sorted_cuisines = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"cuisine": c, "count": n} for c, n in sorted_cuisines[:limit]]
