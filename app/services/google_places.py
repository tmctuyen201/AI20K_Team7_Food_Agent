"""Google Places API client (Phase 2 — motor async wrapper)."""

from __future__ import annotations

from typing import Any

from app.db.models import LatLng, Place
from app.services.client import api_client

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


class PlacesClient:
    """Async client for Google Places Nearby Search."""

    async def search(
        self,
        location: LatLng,
        keyword: str = "restaurant",
        radius: int = 2000,
        open_now: bool = True,
    ) -> list[dict]:
        """Search restaurants near a lat/lng coordinate.

        Args:
            location: LatLng with lat/lng.
            keyword: Search keyword.
            radius: Search radius in metres.
            open_now: Filter only open-now results.

        Returns:
            List of place dicts with basic fields.
        """
        params: dict[str, Any] = {
            "location": f"{location.lat},{location.lng}",
            "radius": radius,
            "keyword": keyword,
            "opennow": open_now,
            "type": "restaurant",
        }

        data = await api_client.get(PLACES_NEARBY_URL, params)

        if data.get("status") == "ZERO_RESULTS":
            return []

        places = []
        for result in data.get("results", [])[:10]:
            places.append({
                "place_id": result.get("place_id", ""),
                "name": result.get("name", ""),
                "rating": result.get("rating", 0.0),
                "distance_km": 0.0,  # calculated separately by scoring tool
                "address": result.get("vicinity", ""),
                "open_now": result.get("opening_hours", {}).get("open_now", False),
            })

        return places


places_client = PlacesClient()
