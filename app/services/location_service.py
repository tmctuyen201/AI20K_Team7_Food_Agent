"""Location resolution service with multi-source fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

import httpx

from app.core.logging import get_tool_logger
from app.services.geocoding import geocode_address
from app.tools.mock_data import get_mock_location

logger = get_tool_logger()


@dataclass
class LocationResult:
    """Result of a location resolution attempt."""

    lat: float
    lng: float
    source: Literal["headers", "geocoding", "mock_data"]
    confidence: float = 1.0
    city: str = ""

    def to_dict(self) -> dict:
        """Return a plain dict for JSON serialization."""
        d = {"lat": self.lat, "lng": self.lng}
        if self.city:
            d["city"] = self.city
        return d


class LocationService:
    """Resolves a user location from GPS headers, address geocoding, or mock data."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        """Close the internal HTTP client if one is held."""
        await self._client.aclose()

    async def get_user_location(
        self,
        user_id: str,
        address: Optional[str] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> LocationResult:
        """Resolve user location using the fallback hierarchy.

        Fallback order:
        1. GPS coordinates from request headers (X-User-Lat / X-User-Lng)
        2. Geocoding ``address`` via Google Geocoding API
        3. Mock data lookup by ``user_id``

        Args:
            user_id: Identifier used for mock-data fallback.
            address: Text address to geocode. Skipped if None/empty.
            headers: Incoming request headers dict. Case-insensitive keys.

        Returns:
            LocationResult with lat, lng, source, and confidence.
        """
        # ── 1. GPS headers ────────────────────────────────────────────────────
        if headers is not None:
            gps_result = self._parse_gps_headers(headers)
            if gps_result is not None:
                logger.info(
                    "location_resolved",
                    source="headers",
                    user_id=user_id,
                    lat=gps_result.lat,
                    lng=gps_result.lng,
                )
                return gps_result

        # ── 2. Geocoding ─────────────────────────────────────────────────────
        if address is not None and address.strip():
            try:
                geo = await geocode_address(address.strip())
                result = LocationResult(
                    lat=geo["lat"],
                    lng=geo["lng"],
                    source="geocoding",
                    confidence=geo.get("confidence", 1.0),
                    city=geo.get("formatted_address", address),
                )
                logger.info(
                    "location_resolved",
                    source="geocoding",
                    user_id=user_id,
                    address=address,
                    lat=result.lat,
                    lng=result.lng,
                    confidence=result.confidence,
                )
                return result
            except Exception:
                # Fallback to mock data silently
                logger.warning(
                    "geocoding_failed_fallback_to_mock",
                    user_id=user_id,
                    address=address,
                )

        # ── 3. Mock data ──────────────────────────────────────────────────────
        mock = get_mock_location(user_id)
        result = LocationResult(
            lat=mock["lat"],
            lng=mock["lng"],
            source="mock_data",
            confidence=0.5,
            city=mock.get("city", ""),
        )
        logger.info(
            "location_resolved",
            source="mock_data",
            user_id=user_id,
            lat=result.lat,
            lng=result.lng,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_gps_headers(headers: dict[str, Any]) -> Optional[LocationResult]:
        """Extract and validate GPS coordinates from a headers dict.

        Looks for ``X-User-Lat`` / ``X-User-Lng`` keys (case-insensitive).
        Returns None if either value is missing, empty, None, or out of range.
        """
        lat_key = next((k for k in headers if k.lower() == "x-user-lat"), None)
        lng_key = next((k for k in headers if k.lower() == "x-user-lng"), None)

        if lat_key is None or lng_key is None:
            return None

        raw_lat = headers.get(lat_key)
        raw_lng = headers.get(lng_key)

        if raw_lat is None or raw_lng is None:
            return None

        # Strip whitespace before parsing; treat empty as invalid
        try:
            lat = float(str(raw_lat).strip())
            lng = float(str(raw_lng).strip())
        except (TypeError, ValueError):
            return None

        if not (-90.0 <= lat <= 90.0):
            logger.warning("gps_header_out_of_range", lat=lat, lng=lng)
            return None
        if not (-180.0 <= lng <= 180.0):
            logger.warning("gps_header_out_of_range", lat=lat, lng=lng)
            return None

        return LocationResult(lat=lat, lng=lng, source="headers", confidence=0.95, city="Current location")
