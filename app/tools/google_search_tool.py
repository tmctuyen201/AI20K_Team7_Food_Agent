"""Google Maps search via SerpAPI — replaces mock Google Places tool."""

from __future__ import annotations

import json
import math
from typing import Any

import requests

from app.core.config import settings
from app.tools.base import BaseTool


class GoogleSearchTool(BaseTool):
    """Search restaurants via SerpAPI Google Maps engine.

    Falls back to empty list if API key is missing or call fails.
    """

    name = "search_google_places"
    description = (
        "Tìm kiếm quán ăn qua Google Maps. Trả về danh sách quán gồm: "
        "name, rating, address, distance_km."
    )

    def _run(
        self,
        location: Any,
        keyword: str = "restaurant",
        radius: int = 2000,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Run the search synchronously.

        Args:
            location: LatLng object or dict with lat/lng.
            keyword:  Food type or restaurant name (e.g. "phở", "bún chả").
            radius:   Search radius in metres (default 2 km).

        Returns:
            List of place dicts compatible with app.db.models.Place.
        """
        api_key = settings.serp_api_key or ""
        if not api_key:
            return self._mock_results(location, keyword)

        # Resolve lat/lng (handles LatLng pydantic model, dict, or raw floats)
        try:
            lat = float(getattr(location, "lat", None) or (location["lat"] if hasattr(location, "__getitem__") else None))
            lng = float(getattr(location, "lng", None) or (location["lng"] if hasattr(location, "__getitem__") else None))
            if lat is None or lng is None:
                raise ValueError("lat/lng not found")
        except (TypeError, ValueError):
            return self._mock_results(location, keyword)

        params = {
            "engine": "google_maps",
            "type": "search",
            "q": keyword,
            "ll": f"@{lat},{lng},16z",
            "hl": "vi",
            "gl": "vn",
            "api_key": api_key,
        }

        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return self._mock_results(location, keyword)

            raw = data.get("local_results") or []
            out = []
            for p in raw:
                gps = p.get("gps_coordinates", {})
                p_lat = gps.get("latitude")
                p_lng = gps.get("longitude")
                dist_km = self._haversine(lat, lng, p_lat, p_lng) if p_lat and p_lng else 999.0

                item = {
                    "place_id": p.get("place_id", ""),
                    "name": p.get("title", "N/A"),
                    "rating": float(p.get("rating") or 0.0),
                    "address": p.get("address", "N/A"),
                    "distance_km": round(dist_km, 2),
                    "latitude": p_lat,
                    "longitude": p_lng,
                    "open_now": p.get("open_state", "").lower() == "open",
                    "price_level": None,
                    "cuisine_type": keyword if keyword != "restaurant" else None,
                    "types": [keyword] if keyword != "restaurant" else ["restaurant"],
                }
                out.append(item)

            # Sort by rating desc, then distance
            out.sort(key=lambda x: (-x["rating"], x["distance_km"]))
            return out[:5]

        except Exception:
            return self._mock_results(location, keyword)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float | None, lng2: float | None) -> float:
        if lat2 is None or lng2 is None:
            return 999.0
        r = 6371.0
        p = math.pi / 180
        a = (
            0.5
            - math.cos((lat2 - lat1) * p) / 2
            + math.cos(lat1 * p)
            * math.cos(lat2 * p)
            * (1 - math.cos((lng2 - lng1) * p)) / 2
        )
        return r * 2 * math.asin(math.sqrt(a))

    @staticmethod
    def _mock_results(location: Any, keyword: str) -> list[dict[str, Any]]:
        """Return mock places when no API key / network is available."""
        try:
            lat = float(getattr(location, "lat", None) or (location["lat"] if hasattr(location, "__getitem__") else 21.0285))
            lng = float(getattr(location, "lng", None) or (location["lng"] if hasattr(location, "__getitem__") else 105.8542))
        except (TypeError, ValueError):
            lat, lng = 21.0285, 105.8542

        mock_data = [
            {
                "place_id": "mock_1",
                "name": f"Quán {keyword or 'ăn'} Ngon 1",
                "rating": 4.5,
                "address": "123 Nguyễn Trãi, Q1, HCM",
                "distance_km": 0.3,
                "latitude": lat + 0.005,
                "longitude": lng + 0.003,
                "open_now": True,
                "price_level": 2,
                "cuisine_type": keyword if keyword != "restaurant" else "Việt Nam",
                "types": [keyword or "restaurant"],
            },
            {
                "place_id": "mock_2",
                "name": f"Nhà hàng {keyword or 'ăn'} 5 sao",
                "rating": 4.8,
                "address": "456 Lê Lợi, Q3, HCM",
                "distance_km": 0.8,
                "latitude": lat + 0.008,
                "longitude": lng + 0.005,
                "open_now": True,
                "price_level": 3,
                "cuisine_type": keyword if keyword != "restaurant" else "Fusion",
                "types": [keyword or "restaurant"],
            },
            {
                "place_id": "mock_3",
                "name": f"Quán {keyword or 'ăn'} Gía Rẻ",
                "rating": 4.1,
                "address": "789 Trần Hưng Đạo, Q5, HCM",
                "distance_km": 1.2,
                "latitude": lat + 0.012,
                "longitude": lng + 0.008,
                "open_now": False,
                "price_level": 1,
                "cuisine_type": keyword if keyword != "restaurant" else "Việt Nam",
                "types": [keyword or "restaurant"],
            },
            {
                "place_id": "mock_4",
                "name": f"Cafe {keyword or 'đặc biệt'}",
                "rating": 4.3,
                "address": "321 Đường 3/2, Q10, HCM",
                "distance_km": 1.5,
                "latitude": lat + 0.015,
                "longitude": lng + 0.010,
                "open_now": True,
                "price_level": 2,
                "cuisine_type": "Cafe",
                "types": ["cafe"],
            },
            {
                "place_id": "mock_5",
                "name": f"Bếp {keyword or 'ăn'} Châu Á",
                "rating": 4.6,
                "address": "555 Pasteur, Q3, HCM",
                "distance_km": 1.8,
                "latitude": lat + 0.018,
                "longitude": lng + 0.012,
                "open_now": True,
                "price_level": 3,
                "cuisine_type": "Châu Á",
                "types": ["restaurant"],
            },
        ]
        return mock_data


google_search_tool = GoogleSearchTool()
