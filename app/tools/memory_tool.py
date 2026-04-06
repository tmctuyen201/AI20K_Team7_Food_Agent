"""Memory tool — persists user restaurant selections to JSON file store."""

from __future__ import annotations

from datetime import datetime

from typing import Any

# Import data_store by absolute path to completely avoid the app.agent package
# and its __init__.py chain (runner → graph → nodes → registry → memory_tool).
import importlib.util
from pathlib import Path

_data_store_path = (
    Path(__file__).resolve().parents[1]      # app/
    / "agent" / "sub_agents" / "data_store.py"
)
_spec = importlib.util.spec_from_file_location("data_store", _data_store_path)
_data_store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_data_store)

find_selection = _data_store.find_selection
insert_selection = _data_store.insert_selection
update_selection = _data_store.update_selection
upsert_user_preference = _data_store.upsert_user_preference
from app.tools.base import BaseTool


class MemoryTool(BaseTool):
    """Save a restaurant selection for a user using JSON file store."""

    name = "save_user_selection"
    description = (
        "Save a restaurant selection when the user chooses a place. "
        "Stores the selection in the file store and updates cuisine preferences."
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
        """Synchronous wrapper — writes directly to JSON file store."""
        now = datetime.utcnow().isoformat()
        selection_data = {
            "user_id": user_id,
            "place_id": place_id,
            "name": name,
            "cuisine_type": cuisine_type,
            "rating": float(rating),
            "selected_at": now,
        }

        existing = find_selection(user_id, place_id)
        if existing:
            update_selection(user_id, place_id, selection_data)
            return {"success": True, "message": "Updated"}
        else:
            insert_selection(selection_data)
            # Also update cuisine preference
            if cuisine_type:
                upsert_user_preference(user_id, {"favorite_cuisine": cuisine_type})
            return {"success": True, "message": "Saved"}


memory_tool = MemoryTool()
