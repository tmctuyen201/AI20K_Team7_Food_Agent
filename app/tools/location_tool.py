"""Location tool — resolves user lat/lng from headers, address, or mock data."""

from __future__ import annotations

from typing import Any

from app.db.models import LatLng, LocationResult
from app.db.mock_data import get_mock_location, DEFAULT_LOCATION
from app.tools.base import BaseTool


class LocationTool(BaseTool):
    """Resolve a user's geographic location.

    Resolution order:
      1. GPS headers (X-User-Lat / X-User-Lng)
      2. Address string → geocoding
      3. Mock data for known user IDs
      4. Default Hanoi location
    """

    name = "get_user_location"
    description = "Get the current latitude and longitude for a user. Returns lat/lng, source, and confidence."

    def _run(
        self,
        user_id: str,
        address: str | None = None,
        headers: dict | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # Priority 1: GPS headers
        if headers:
            lat = headers.get("X-User-Lat") or headers.get("x-user-lat")
            lng = headers.get("X-User-Lng") or headers.get("x-user-lng")
            if lat and lng:
                try:
                    return {
                        "lat": float(lat),
                        "lng": float(lng),
                        "source": "headers",
                        "confidence": 0.95,
                    }
                except ValueError:
                    pass

        # Priority 2: Address → geocoding
        # (defer to async layer in production; sync _run uses mock)
        if address:
            # TODO: call geocoding_client.geocode(address) in async context
            pass

        # Priority 3: Mock data
        mock_loc = get_mock_location(user_id)
        return {
            "lat": mock_loc.lat,
            "lng": mock_loc.lng,
            "source": "mock_data",
            "confidence": 0.5,
        }


location_tool = LocationTool()
