"""Pytest fixtures for location service and geocoding tests."""

import pytest
import pytest_asyncio
import httpx

from app.services.location_service import LocationService, LocationResult


# ---------------------------------------------------------------------------
# Location service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def location_service() -> LocationService:
    """Return a fresh LocationService instance."""
    return LocationService()


@pytest.fixture
def valid_headers() -> dict[str, str]:
    """Return headers with valid numeric coordinates (Hà Nội, Việt Nam)."""
    return {
        "X-User-Lat": "21.0285",
        "X-User-Lng": "105.8542",
    }


@pytest.fixture
def invalid_headers() -> dict[str, str]:
    """Return headers with non-numeric values."""
    return {
        "x-user-lat": "not-a-number",
        "x-user-lng": "also-not-a-number",
    }


@pytest.fixture
def out_of_range_headers() -> dict[str, str]:
    """Return headers with latitude out of valid range."""
    return {
        "X-User-Lat": "200",
        "X-User-Lng": "105.8542",
    }


@pytest.fixture
def empty_headers() -> dict[str, str]:
    """Return an empty headers dict."""
    return {}


@pytest.fixture
def mock_location_result() -> LocationResult:
    """Return a LocationResult for use in unit tests."""
    return LocationResult(lat=40.7128, lng=-74.0060)


# ---------------------------------------------------------------------------
# HTTP client fixture (for geocoding client integration tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client() -> httpx.AsyncClient:
    """Yield an httpx AsyncClient and close it after the test."""
    async with httpx.AsyncClient() as client:
        yield client


# ---------------------------------------------------------------------------
# Pytest asyncio plugin
# ---------------------------------------------------------------------------

pytest_plugins = ["pytest_asyncio"]
