"""Geocoding API client using Nominatim (OpenStreetMap) — no API key required."""

from __future__ import annotations

from typing import Any

from app.services.client import api_client

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class GeocodingClient:
    """Async geocoding client backed by OpenStreetMap Nominatim."""

    async def geocode(self, address: str) -> dict[str, Any]:
        """Convert a text address to lat/lng via Nominatim.

        Args:
            address: Human-readable address string.

        Returns:
            Dict with lat, lng, and confidence score.
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

        # Use a plain httpx call so we can inject custom headers
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)

        data = response.json()

        if not data:
            # Fallback to default Hanoi location
            return {"lat": 21.0285, "lng": 105.8542, "confidence": 0.5}

        result = data[0]
        lat = float(result["lat"])
        lng = float(result["lon"])

        importance = float(result.get("importance", 0.5))
        confidence = min(0.5 + importance * 0.5, 1.0)

        return {
            "lat": lat,
            "lng": lng,
            "confidence": confidence,
        }


geocoding_client = GeocodingClient()
