"""Test suite for LocationService — 3-tier priority: GPS headers → Geocoding → Mock data."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import GeocodingAPIError
from app.services.location_service import LocationService, LocationResult
from app.tools.mock_data import MOCK_USERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def location_service() -> LocationService:
    return LocationService()


@pytest.fixture
def valid_headers() -> dict:
    return {"X-User-Lat": "21.0285", "X-User-Lng": "105.8542"}


@pytest.fixture
def invalid_headers() -> dict:
    return {"X-User-Lat": "not_a_number", "X-User-Lng": "106.7009"}


@pytest.fixture
def out_of_range_headers() -> dict:
    return {"X-User-Lat": "200.0", "X-User-Lng": "105.8542"}


# ---------------------------------------------------------------------------
# TestGPSHeaders — Priority 1
# ---------------------------------------------------------------------------

class TestGPSHeaders:
    @pytest.mark.asyncio
    async def test_valid_headers_returns_location_from_headers(
        self, location_service: LocationService, valid_headers: dict
    ) -> None:
        result = await location_service.get_user_location("u01", headers=valid_headers)
        assert result.source == "headers"
        assert result.lat == pytest.approx(21.0285)
        assert result.lng == pytest.approx(105.8542)
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_case_insensitive_headers(self, location_service: LocationService) -> None:
        headers = {"x-user-lat": "10.7769", "x-user-lng": "106.7009"}
        result = await location_service.get_user_location("u01", headers=headers)
        assert result.source == "headers"
        assert result.lat == pytest.approx(10.7769)
        assert result.lng == pytest.approx(106.7009)

    @pytest.mark.asyncio
    async def test_invalid_numeric_format_fallback_to_mock(
        self, location_service: LocationService, invalid_headers: dict
    ) -> None:
        result = await location_service.get_user_location("u01", headers=invalid_headers)
        assert result.source == "mock_data"
        assert result.lat == pytest.approx(21.0285)
        assert result.lng == pytest.approx(105.8542)

    @pytest.mark.asyncio
    async def test_out_of_range_coordinates_fallback_to_mock(
        self, location_service: LocationService, out_of_range_headers: dict
    ) -> None:
        result = await location_service.get_user_location("u02", headers=out_of_range_headers)
        assert result.source == "mock_data"
        assert result.lat == pytest.approx(10.7769)
        assert result.lng == pytest.approx(106.7009)

    @pytest.mark.asyncio
    async def test_missing_headers_continues_to_next_source(
        self, location_service: LocationService
    ) -> None:
        # No headers at all → should fall through to mock (no address provided)
        result = await location_service.get_user_location("u03")
        assert result.source == "mock_data"

    @pytest.mark.asyncio
    async def test_headers_with_whitespace(self, location_service: LocationService) -> None:
        headers = {"X-User-Lat": "  16.0544  ", "X-User-Lng": "  108.2022  "}
        result = await location_service.get_user_location("u01", headers=headers)
        # If the implementation trims whitespace it returns headers, otherwise fallback
        # Assumes implementation trims before float() call
        assert result.source == "headers"
        assert result.lat == pytest.approx(16.0544)
        assert result.lng == pytest.approx(108.2022)

    @pytest.mark.asyncio
    async def test_boundary_coordinates(self, location_service: LocationService) -> None:
        headers = {"X-User-Lat": "90", "X-User-Lng": "180"}
        result = await location_service.get_user_location("u01", headers=headers)
        assert result.source == "headers"
        assert result.lat == pytest.approx(90.0)
        assert result.lng == pytest.approx(180.0)

    @pytest.mark.asyncio
    async def test_none_values_in_headers_ignored(self, location_service: LocationService) -> None:
        headers: dict[str, Any] = {"X-User-Lat": None, "X-User-Lng": None}
        result = await location_service.get_user_location("u04", headers=headers)
        assert result.source == "mock_data"


# ---------------------------------------------------------------------------
# TestGeocoding — Priority 2
# ---------------------------------------------------------------------------

class TestGeocoding:
    @pytest.mark.asyncio
    async def test_successful_geocoding(self, location_service: LocationService) -> None:
        mock_result = {"lat": 16.0544, "lng": 108.2022, "confidence": 0.9, "formatted_address": "Da Nang"}
        with patch(
            "app.services.location_service.geocode_address",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_geocode:
            result = await location_service.get_user_location(
                "u01", address="123 Nguyen Tri, Da Nang", headers={}
            )
            assert result.source == "geocoding"
            assert result.lat == pytest.approx(16.0544)
            assert result.lng == pytest.approx(108.2022)
            assert result.confidence == 0.9
            mock_geocode.assert_called_once_with("123 Nguyen Tri, Da Nang")

    @pytest.mark.asyncio
    async def test_geocoding_error_fallback_to_mock(self, location_service: LocationService) -> None:
        with patch(
            "app.services.location_service.geocode_address",
            new_callable=AsyncMock,
            side_effect=GeocodingAPIError("API failed"),
        ):
            result = await location_service.get_user_location(
                "u05", address="Hai Phong", headers={}
            )
            assert result.source == "mock_data"
            assert result.lat == pytest.approx(20.8449)
            assert result.lng == pytest.approx(106.6881)

    @pytest.mark.asyncio
    async def test_no_address_skips_geocoding(self, location_service: LocationService) -> None:
        with patch(
            "app.services.location_service.geocode_address",
            new_callable=AsyncMock,
        ) as mock_geocode:
            result = await location_service.get_user_location(
                "u06", address=None, headers={}
            )
            assert result.source == "mock_data"
            mock_geocode.assert_not_called()


# ---------------------------------------------------------------------------
# TestMockData — Priority 3
# ---------------------------------------------------------------------------

class TestMockData:
    @pytest.mark.asyncio
    async def test_known_user_returns_correct_mock_location(self, location_service: LocationService) -> None:
        result = await location_service.get_user_location("u01")
        assert result.source == "mock_data"
        assert result.lat == pytest.approx(21.0285)
        assert result.lng == pytest.approx(105.8542)

    @pytest.mark.asyncio
    async def test_unknown_user_returns_default_location(self, location_service: LocationService) -> None:
        result = await location_service.get_user_location("u99")
        # Falls back to u01 (Hà Nội)
        assert result.source == "mock_data"
        assert result.lat == pytest.approx(21.0285)
        assert result.lng == pytest.approx(105.8542)

    @pytest.mark.asyncio
    async def test_all_10_mock_users_work(self, location_service: LocationService) -> None:
        expected = [
            ("u01", 21.0285, 105.8542),
            ("u02", 10.7769, 106.7009),
            ("u03", 16.0544, 108.2022),
            ("u04", 10.0341, 105.7852),
            ("u05", 20.8449, 106.6881),
            ("u06", 10.9574, 106.8426),
            ("u07", 21.5944, 105.8412),
            ("u08", 12.2388, 109.1967),
            ("u09", 13.7830, 109.2194),
            ("u10", 11.9465, 108.4419),
        ]
        for user_id, exp_lat, exp_lng in expected:
            result = await location_service.get_user_location(user_id)
            assert result.lat == pytest.approx(exp_lat), f"u01 mismatch for {user_id}"
            assert result.lng == pytest.approx(exp_lng), f"u02 mismatch for {user_id}"


# ---------------------------------------------------------------------------
# TestFullFlow — Integration
# ---------------------------------------------------------------------------

class TestFullFlow:
    @pytest.mark.asyncio
    async def test_complete_happy_path_with_all_sources(
        self, location_service: LocationService, valid_headers: dict
    ) -> None:
        """When all 3 sources are present, headers (Priority 1) wins."""
        mock_result = {"lat": 99.0, "lng": 99.0, "confidence": 0.5}
        with patch(
            "app.services.location_service.geocode_address",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_geocode:
            result = await location_service.get_user_location(
                "u01", address="Any address", headers=valid_headers
            )
            assert result.source == "headers"
            assert result.lat == pytest.approx(21.0285)
            mock_geocode.assert_not_called()  # geocoding should NOT be called

    @pytest.mark.asyncio
    async def test_headers_priority_over_geocoding(
        self, location_service: LocationService, valid_headers: dict
    ) -> None:
        mock_result = {"lat": 99.0, "lng": 99.0, "confidence": 0.5}
        with patch(
            "app.services.location_service.geocode_address",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_geocode:
            await location_service.get_user_location(
                "u02", address="Somewhere", headers=valid_headers
            )
            mock_geocode.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_headers_dict_treated_as_missing(self, location_service: LocationService) -> None:
        # {} is falsy in the stub implementation — falls through to mock
        result = await location_service.get_user_location("u07", headers={})
        assert result.source == "mock_data"
        assert result.lat == pytest.approx(21.5944)