"""Shared HTTP client for external API calls."""

from __future__ import annotations

from typing import Optional

import httpx


class GoogleAPIClient:
    """Thin async HTTP wrapper that attaches the Google API key to every request."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key: str = api_key or ""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get(self, url: str, params: dict) -> dict:
        """Send a GET request with the API key injected."""
        request_params = {**params, "key": self.api_key}
        response = await self.client.get(url, params=request_params)
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()


# Global singleton — shared across all service modules
api_client = GoogleAPIClient()
