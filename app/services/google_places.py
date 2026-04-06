"""Google Places API client with logging."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import PlacesAPIError
from app.core.logging import get_logger

logger = get_logger("foodie.google_places")

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACES_DETAIL_URL = "https://maps.googleapis.com/maps/api/place/details/json"


async def search_places(
    lat: float,
    lng: float,
    keyword: str = "restaurant",
    sort_by: str = "prominence",
    radius: int = 2000,
    open_now: bool = True,
    next_page_token: str | None = None,
) -> list[dict[str, Any]]:
    """Search Google Places Nearby Search API.

    Args:
        lat: Latitude
        lng: Longitude
        keyword: Search keyword
        sort_by: "prominence" or "distance"
        radius: Search radius in meters
        open_now: Filter only open now
        next_page_token: For pagination

    Returns:
        List of raw place dicts from the API.

    Raises:
        PlacesAPIError: On API failure.
    """
    params: dict[str, Any] = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "keyword": keyword,
        "opennow": open_now,
        "key": settings.google_places_api_key,
    }

    if sort_by == "distance":
        params["rankby"] = "distance"
    else:
        params["rankby"] = sort_by  # prominence

    if next_page_token:
        params["pagetoken"] = next_page_token

    logger.info(
        "google_places_search",
        lat=lat,
        lng=lng,
        keyword=keyword,
        sort_by=sort_by,
        radius=radius,
        open_now=open_now,
        has_page_token=bool(next_page_token),
    )

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(PLACES_NEARBY_URL, params=params)

        elapsed_ms = (time.monotonic() - start) * 1000
        data = response.json()

        status = data.get("status", "UNKNOWN")
        results = data.get("results", [])
        next_token = data.get("next_page_token")

        logger.info(
            "google_places_response",
            status=status,
            results_count=len(results),
            has_next_token=bool(next_token),
            elapsed_ms=round(elapsed_ms, 1),
        )

        if status in ("ZERO_RESULTS", "INVALID_REQUEST"):
            return []
        if status != "OK":
            raise PlacesAPIError(f"Places API error: {status}")

        # Attach next_page_token in first result for pagination
        if next_token and results:
            results[0]["_next_page_token"] = next_token

        return results

    except httpx.HTTPError as e:
        logger.error(
            "google_places_http_error",
            error=str(e),
            elapsed_ms=round((time.monotonic() - start) * 1000, 1),
        )
        raise PlacesAPIError(f"HTTP error calling Places API: {e}") from e


async def get_place_details(place_id: str) -> dict[str, Any]:
    """Get detailed info for a single place.

    Args:
        place_id: Google place ID.

    Returns:
        Full place detail dict.
    """
    params = {
        "place_id": place_id,
        "fields": "place_id,name,rating,formatted_address,geometry,"
                  "opening_hours,photos,price_level,types,reviews",
        "key": settings.google_places_api_key,
    }

    logger.info(
        "google_places_detail",
        place_id=place_id,
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(PLACES_DETAIL_URL, params=params)

    data = response.json()
    if data.get("status") != "OK":
        raise PlacesAPIError(f"Place detail error: {data.get('status')}")

    return data.get("result", {})
