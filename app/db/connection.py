"""MongoDB connection management using Motor (async driver)."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = None


def _get_logger():
    global logger
    if logger is None:
        from app.core.logging import get_logger
        logger = get_logger("foodie.db")
    return logger


class Database:
    client: AsyncIOMotorClient | None = None
    db_name: str = "foodie"


_db = Database()


async def connect_db() -> None:
    """Initialise the MongoDB client and create indexes."""
    _db.client = AsyncIOMotorClient(settings.mongodb_uri)
    log = _get_logger()
    log.info("mongodb_connecting", uri=settings.mongodb_uri)

    # Resolve the actual database name from the URI path component
    # e.g. "mongodb://host:27017/foodie_agent"  ->  "foodie_agent"
    uri_db = _resolve_db_name(settings.mongodb_uri)
    if uri_db:
        _db.db_name = uri_db

    # Create indexes
    db = _db.client[_db.db_name]
    await db.users.create_index("user_id", unique=True)
    await db.sessions.create_index("session_id", unique=True)
    await db.selections.create_index([("user_id", 1), ("place_id", 1)], unique=True)
    await db.selections.create_index([("user_id", 1), ("selected_at", -1)])

    log.info("mongodb_connected", database=_db.db_name)


async def close_db() -> None:
    """Close the MongoDB client."""
    if _db.client:
        _db.client.close()
        _get_logger().info("mongodb_closed")


def get_db() -> AsyncIOMotorDatabase:
    """Return the foodie database instance."""
    if _db.client is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _db.client[_db.db_name]


def _resolve_db_name(uri: str) -> str | None:
    """Extract database name from a MongoDB URI string."""
    # URI format: mongodb://host:port/DBNAME
    parts = uri.rsplit("/", 1)
    if len(parts) == 2 and parts[1]:
        # Strip any trailing options (query string)
        db_part = parts[1].split("?")[0]
        return db_part if db_part else None
    return None