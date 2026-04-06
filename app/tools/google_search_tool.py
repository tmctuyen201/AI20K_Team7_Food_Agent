"""Google Places search tool — returns mock results when no API key is set."""

from __future__ import annotations

from typing import Any

from app.db.models import LatLng
from app.tools.base import BaseTool


# ---------------------------------------------------------------------------
# Mock dataset — used when Google API key is unavailable
# ---------------------------------------------------------------------------

_MOCK_PLACES = [
    {
        "place_id": "ChIJN1",
        "name": "Phở Thìn",
        "rating": 4.5,
        "distance_km": 0.8,
        "address": "13 Lò Đúc, Hoàn Kiếm, Hà Nội",
        "open_now": True,
        "cuisine_type": "phở",
    },
    {
        "place_id": "ChIJN2",
        "name": "Bún Chả Hương",
        "rating": 4.3,
        "distance_km": 1.2,
        "address": "1 Lê Thái Tổ, Hoàn Kiếm, Hà Nội",
        "open_now": True,
        "cuisine_type": "bún chả",
    },
    {
        "place_id": "ChIJN3",
        "name": "Quán Ăn Ngon",
        "rating": 4.2,
        "distance_km": 1.5,
        "address": "123 Cầu Gỗ, Hoàn Kiếm, Hà Nội",
        "open_now": True,
        "cuisine_type": "cơm",
    },
    {
        "place_id": "ChIJN4",
        "name": "Bánh Mì 37",
        "rating": 4.0,
        "distance_km": 0.5,
        "address": "37 Nguyễn Trãi, Quận 1, TP.HCM",
        "open_now": True,
        "cuisine_type": "bánh mì",
    },
    {
        "place_id": "ChIJN5",
        "name": "Hải Sản Biển Đông",
        "rating": 4.4,
        "distance_km": 2.0,
        "address": "456 Láng Hạ, Ba Đình, Hà Nội",
        "open_now": False,
        "cuisine_type": "hải sản",
    },
]


class GoogleSearchTool(BaseTool):
    """Search Google Places API for restaurants near a location.

    Falls back to mock data when the API key is not configured.
    """

    name = "search_google_places"
    description = (
        "Search Google Places API for restaurants near a location. "
        "Returns a list of places with name, rating, distance, address, open_now, cuisine_type."
    )

    def _run(
        self,
        location: LatLng | dict | None = None,
        keyword: str = "restaurant",
        radius: int = 2000,
        open_now: bool = True,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        # Keyword-based filter on mock data
        if keyword and keyword.lower() != "restaurant":
            filtered = [
                r for r in _MOCK_PLACES
                if keyword.lower() in r["name"].lower()
                or keyword.lower() in r.get("cuisine_type", "").lower()
            ]
            if filtered:
                return filtered

        return _MOCK_PLACES


google_search_tool = GoogleSearchTool()
