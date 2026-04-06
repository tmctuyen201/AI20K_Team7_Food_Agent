"""Geocoding API client — Nominatim (OpenStreetMap), no API key required."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.exceptions import GeocodingAPIError
from app.core.logging import get_logger

logger = get_logger("foodie.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode_address(address: str) -> dict[str, Any]:
    """Convert a text address to lat/lng via Nominatim (OpenStreetMap).

    Args:
        address: Human-readable address string.

    Returns:
        Dict with lat, lng, and confidence score.

    Raises:
        GeocodingAPIError: On API failure or zero results.
    """
    params = {
        "q": address,
        "format": "json",
        "limit": "1",
        "addressdetails": "1",
    }
    headers = {
        "User-Agent": "FoodieAgent/1.0 (vinai.chatbot)",
    }

    logger.info("geocoding_request", address=address, provider="nominatim")

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(NOMINATIM_URL, params=params, headers=headers)

    elapsed_ms = (time.monotonic() - start) * 1000
    data = response.json()

    if not data:
        raise GeocodingAPIError(f"No results for address: {address}")

    result = data[0]
    lat = float(result["lat"])
    lng = float(result["lon"])
    display_name = result.get("display_name", address)

    # Nominatim doesn't expose a numeric confidence — estimate from importance field
    importance = float(result.get("importance", 0.5))
    confidence = min(0.5 + importance * 0.5, 1.0)

    logger.info(
        "geocoding_success",
        address=address,
        lat=lat,
        lng=lng,
        display_name=display_name,
        confidence=confidence,
        provider="nominatim",
        elapsed_ms=round(elapsed_ms, 1),
    )

    return {
        "lat": lat,
        "lng": lng,
        "confidence": confidence,
        "formatted_address": display_name,
    }
