"""MongoDB connection management using Motor (async driver)."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("foodie.db.connection")

_DB_NAME = "foodie"


class _Database:
    client: AsyncIOMotorClient | None = None


_db = _Database()


async def connect_db() -> None:
    """Initialise the MongoDB client and create indexes."""
    _db.client = AsyncIOMotorClient(settings.mongodb_uri)
    logger.info("mongodb_connecting", uri=settings.mongodb_uri)

    db = _db.client[_DB_NAME]

    # Create indexes
    await db.users.create_index("user_id", unique=True)
    await db.sessions.create_index("session_id", unique=True)
    await db.selections.create_index([("user_id", 1), ("place_id", 1)], unique=True)
    await db.selections.create_index([("user_id", 1), ("selected_at", -1)])

    logger.info("mongodb_connected", database=_DB_NAME)


async def close_db() -> None:
    """Close the MongoDB client."""
    if _db.client:
        _db.client.close()
        logger.info("mongodb_closed")


def get_db() -> AsyncIOMotorDatabase:
    """Return the foodie database instance."""
    if _db.client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db.client[_DB_NAME]
