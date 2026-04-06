"""Low-level MongoDB query helpers (Phase 2)."""

from __future__ import annotations

from typing import Optional

from app.db.connection import get_db
from app.db.models import Session, Selection, User, UserPreference


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


async def get_user(user_id: str) -> Optional[User]:
    """Retrieve a user by user_id, or None if not found."""
    doc = await get_db().users.find_one({"user_id": user_id})
    return User(**doc) if doc else None


async def create_user(user: User) -> bool:
    """Insert a new user document. Returns True on success."""
    try:
        user_dict = user.model_dump()
        # Remove None lat/lng from default_location to avoid validation errors
        loc = user_dict.get("default_location")
        if loc and loc.get("lat") == 0.0 and loc.get("lng") == 0.0:
            user_dict["default_location"] = {"lat": loc["lat"], "lng": loc["lng"]}
        await get_db().users.insert_one(user_dict)
        return True
    except Exception:
        return False


async def upsert_user(user_id: str, name: str = "", lat: float = 0.0, lng: float = 0.0, city: str = "") -> None:
    """Insert or replace a user document."""
    await get_db().users.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "name": name, "lat": lat, "lng": lng, "city": city}},
        upsert=True,
    )


async def get_user_preference(user_id: str) -> UserPreference:
    """Return the user's preference sub-document."""
    doc = await get_db().users.find_one(
        {"user_id": user_id},
        {"preference": 1},
    )
    if doc and "preference" in doc:
        return UserPreference(**doc["preference"])
    return UserPreference()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


async def get_session(session_id: str) -> Optional[Session]:
    """Retrieve a session by session_id."""
    doc = await get_db().sessions.find_one({"session_id": session_id})
    return Session(**doc) if doc else None


async def create_session(session: Session) -> bool:
    """Insert a new session document."""
    try:
        await get_db().sessions.insert_one(session.model_dump())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


async def save_selection(selection: Selection, update_preference: bool = True) -> bool:
    """Insert a restaurant selection. Optionally update the user's cuisine preference."""
    try:
        await get_db().selections.insert_one(selection.model_dump())

        if update_preference and selection.cuisine_type:
            await get_db().users.update_one(
                {"user_id": selection.user_id},
                {"$addToSet": {"preference.favorite_cuisines": selection.cuisine_type}},
            )

        return True
    except Exception:
        return False


async def get_user_selections(
    user_id: str,
    limit: int = 20,
    skip: int = 0,
) -> list[Selection]:
    """Return the most recent selections for a user."""
    cursor = (
        get_db()
        .selections.find({"user_id": user_id})
        .sort("selected_at", -1)
        .skip(skip)
        .limit(limit)
    )
    selections = []
    async for doc in cursor:
        selections.append(Selection(**doc))
    return selections


async def get_selection_count(user_id: str) -> int:
    """Return the total number of selections for a user."""
    return await get_db().selections.count_documents({"user_id": user_id})


async def get_top_cuisines(user_id: str, limit: int = 5) -> list[dict]:
    """Return the user's most-frequently selected cuisines."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$cuisine_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    result = []
    async for doc in get_db().selections.aggregate(pipeline):
        result.append({"cuisine": doc["_id"], "count": doc["count"]})
    return result
