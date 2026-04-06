"""Google Geocoding API client."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import GeocodingAPIError
from app.core.logging import get_logger

logger = get_logger("foodie.geocoding")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def geocode_address(address: str) -> dict[str, Any]:
    """Convert a text address to lat/lng via Google Geocoding API.

    Args:
        address: Human-readable address string.

    Returns:
        Dict with lat, lng, and confidence score.

    Raises:
        GeocodingAPIError: On API failure or zero results.
    """
    params = {
        "address": address,
        "key": settings.google_geocoding_api_key or settings.google_places_api_key,
    }

    logger.info(
        "geocoding_request",
        address=address,
    )

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(GEOCODE_URL, params=params)

    elapsed_ms = (time.monotonic() - start) * 1000
    data = response.json()

    status = data.get("status", "UNKNOWN")

    if status == "ZERO_RESULTS":
        raise GeocodingAPIError(f"No results for address: {address}")

    if status != "OK":
        raise GeocodingAPIError(f"Geocoding API error: {status}")

    result = data["results"][0]
    location = result["geometry"]["location"]
    confidence = 1.0  # Google doesn't expose confidence score directly

    logger.info(
        "geocoding_success",
        address=address,
        lat=location["lat"],
        lng=location["lng"],
        confidence=confidence,
        elapsed_ms=round(elapsed_ms, 1),
    )

    return {
        "lat": location["lat"],
        "lng": location["lng"],
        "confidence": confidence,
        "formatted_address": result.get("formatted_address", address),
    }
