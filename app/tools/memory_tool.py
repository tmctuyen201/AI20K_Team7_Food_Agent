"""Memory tool — persists user restaurant selections to MongoDB."""

from __future__ import annotations

from typing import Any

from app.db.models import Selection
from app.db.queries import save_selection as _db_save_selection
from app.tools.base import BaseTool


class MemoryTool(BaseTool):
    """Save a restaurant selection for a user."""

    name = "save_user_selection"
    description = (
        "Save a restaurant selection when the user chooses a place. "
        "Stores the selection in the database and updates cuisine preferences."
    )

    def _run(
        self,
        user_id: str,
        place_id: str,
        name: str,
        cuisine_type: str | None = None,
        rating: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Synchronous wrapper — runs the async save in an event loop."""
        import asyncio
        from datetime import datetime

        selection = Selection(
            user_id=user_id,
            place_id=place_id,
            name=name,
            cuisine_type=cuisine_type,
            rating=float(rating),
            selected_at=datetime.utcnow(),
        )

        # Run async DB call in the current event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — create one
            result = asyncio.run(_db_save_selection(selection, update_preference=True))
            return {"success": result, "message": "Saved" if result else "Failed"}

        # Schedule the coroutine in the running loop
        future = asyncio.ensure_future(
            _db_save_selection(selection, update_preference=True)
        )
        # Block until complete (only safe in a thread context)
        result = asyncio.run_coroutine_threadsafe(future, loop).result(timeout=10)
        return {"success": result, "message": "Saved" if result else "Failed"}


memory_tool = MemoryTool()
