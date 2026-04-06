"""Google Places API client (Phase 2 — motor async wrapper)."""

from __future__ import annotations

from typing import Any

import httpx

from app.db.models import LatLng, Place
from app.services.client import api_client
from app.core.logging import get_logger

logger = get_logger("foodie.places")

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

        try:
            data = await api_client.get(PLACES_NEARBY_URL, params)
        except httpx.TimeoutException:
            logger.error(
                "google_places_timeout",
                location=f"{location.lat},{location.lng}",
                keyword=keyword,
                radius=radius,
            )
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                "google_places_http_error",
                status_code=e.response.status_code,
                location=f"{location.lat},{location.lng}",
                keyword=keyword,
            )
            return []
        except Exception as e:
            logger.error(
                "google_places_unknown_error",
                error=str(e),
                location=f"{location.lat},{location.lng}",
                keyword=keyword,
            )
            return []

        if data.get("status") == "ZERO_RESULTS":
            logger.info(
                "google_places_zero_results",
                keyword=keyword,
                location=f"{location.lat},{location.lng}",
            )
            return []

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(
                "google_places_unexpected_status",
                status=data.get("status"),
                keyword=keyword,
            )
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
                "opening_hours": result.get("opening_hours", {}),
            })

        logger.info(
            "google_places_search_success",
            count=len(places),
            keyword=keyword,
            location=f"{location.lat},{location.lng}",
        )

        return places


places_client = PlacesClient()
