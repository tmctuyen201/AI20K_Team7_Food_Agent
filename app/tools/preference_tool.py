"""Preference tool — reads user preferences and selection history."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool

# Lazily import data_store to avoid circular imports
_data_store: Any = None


def _get_data_store() -> Any:
    global _data_store
    if _data_store is None:
        spec = importlib.util.spec_from_file_location(
            "data_store",
            Path(__file__).resolve().parents[1]
            / "agent" / "sub_agents" / "data_store.py",
        )
        _data_store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_data_store)
    return _data_store


class PreferenceTool(BaseTool):
    """Get user preferences and selection history for personalized recommendations."""

    name = "get_user_preference"
    description = (
        "Lấy lịch sử lựa chọn và sở thích của người dùng: "
        "favorite_cuisines, avoid_cuisines, price_range, preferred_ambiance, "
        "tổng số quán đã chọn, rating trung bình. "
        "Dùng K� antescore để cá nhân hóa kết quả tìm kiếm."
    )

    def _run(
        self,
        user_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        ds = _get_data_store()

        # Get structured preferences
        pref = ds.get_user_preference(user_id)

        # Get recent selections for analysis
        selections = ds.list_selections(user_id, limit=50)

        # Compute aggregate stats
        total = len(selections)
        avg_rating = 0.0
        cuisine_count: dict[str, int] = {}
        distance_preference = "unknown"  # not yet tracked

        if total > 0:
            ratings = [s.get("rating", 0.0) for s in selections if s.get("rating")]
            avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

            for sel in selections:
                cuisine = sel.get("cuisine_type") or "unknown"
                cuisine_count[cuisine] = cuisine_count.get(cuisine, 0) + 1

        # Top cuisine = most selected
        top_cuisine = (
            max(cuisine_count, key=cuisine_count.get) if cuisine_count else None
        )

        return {
            "user_id": user_id,
            "favorite_cuisines": pref.get("favorite_cuisines", []),
            "avoid_cuisines": pref.get("avoid_cuisines", []),
            "price_range": pref.get("price_range", "mid"),
            "preferred_ambiance": pref.get("preferred_ambiance"),
            "total_selections": total,
            "avg_rating": avg_rating,
            "top_cuisine": top_cuisine,
            "cuisine_distribution": cuisine_count,
            "has_history": total > 0,
        }


preference_tool = PreferenceTool()
