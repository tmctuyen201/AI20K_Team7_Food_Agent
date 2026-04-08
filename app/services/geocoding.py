"""Geocoding API client using Nominatim (OpenStreetMap) — no API key required."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("foodie.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Default fallback location (Hà Nội)
DEFAULT_FALLBACK = {"lat": 21.0285, "lng": 105.8542, "confidence": 0.5}


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

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(NOMINATIM_URL, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("geocoding_timeout", address=address)
            return DEFAULT_FALLBACK.copy()
        except httpx.HTTPStatusError as e:
            logger.error(
                "geocoding_http_error",
                address=address,
                status_code=e.response.status_code,
            )
            return DEFAULT_FALLBACK.copy()
        except Exception as e:
            logger.error("geocoding_unknown_error", address=address, error=str(e))
            return DEFAULT_FALLBACK.copy()

        if not data:
            logger.warning("geocoding_no_results", address=address)
            return DEFAULT_FALLBACK.copy()

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

    async def geocode_with_suggestions(self, address: str) -> dict[str, Any]:
        """Convert a text address to lat/lng and return multiple candidates.

        Used for ambiguous addresses (e.g. "Phố Huế" → multiple cities).

        Returns:
            Dict with first_result, all_results list, and ambiguous flag.
        """
        params = {
            "q": address,
            "format": "json",
            "limit": "5",
            "addressdetails": "1",
        }
        headers = {
            "User-Agent": "FoodieAgent/1.0 (vinai.chatbot)",
        }

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(NOMINATIM_URL, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("geocoding_timeout", address=address)
            return {"first_result": DEFAULT_FALLBACK.copy(), "all_results": [], "ambiguous": False}
        except httpx.HTTPStatusError as e:
            logger.error("geocoding_http_error", address=address, status_code=e.response.status_code)
            return {"first_result": DEFAULT_FALLBACK.copy(), "all_results": [], "ambiguous": False}
        except Exception as e:
            logger.error("geocoding_unknown_error", address=address, error=str(e))
            return {"first_result": DEFAULT_FALLBACK.copy(), "all_results": [], "ambiguous": False}

        if not data:
            return {"first_result": DEFAULT_FALLBACK.copy(), "all_results": [], "ambiguous": False}

        all_results = []
        for item in data:
            lat = float(item["lat"])
            lng = float(item["lon"])
            importance = float(item.get("importance", 0.5))
            confidence = min(0.5 + importance * 0.5, 1.0)
            display_name = item.get("display_name", address)
            all_results.append({
                "lat": lat,
                "lng": lng,
                "confidence": confidence,
                "display_name": display_name,
            })

        # Check for ambiguity: same name in multiple different cities/regions
        regions = set()
        for item in data:
            addr = item.get("address") or {}
            region = addr.get("state") or addr.get("city") or addr.get("town") or addr.get("village") or ""
            if region:
                regions.add(region)

        ambiguous = len(regions) > 1 and len(all_results) > 1

        return {
            "first_result": all_results[0],
            "all_results": all_results,
            "ambiguous": ambiguous,
        }


geocoding_client = GeocodingClient()


def geocode_address(address: str) -> dict[str, Any]:
    """Synchronous wrapper for backward compatibility.

    Runs the async geocode method in a new event loop.
    Prefer the async GeocodingClient.geocode() in async contexts.
    """
    import asyncio
    return asyncio.run(geocoding_client.geocode(address))