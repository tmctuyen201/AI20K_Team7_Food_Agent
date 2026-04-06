"""Tests for the get_user_location tool integration.

Covers:
- Tool schema correctness in app/tools/definitions.py
- ReActAgent._tool_get_user_location using LocationService
- Full end-to-end resolution flows (headers → geocoding → mock)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.react_agent import ReActAgent
from app.agent.state import AgentState
from app.services.location_service import LocationResult
from app.tools.definitions import get_tool_definitions


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_location_tool_def() -> dict:
    """Return the get_user_location tool definition dict."""
    tools = get_tool_definitions()
    return next(
        t for t in tools
        if t["function"]["name"] == "get_user_location"
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_location_service():
    """LocationService whose get_user_location always returns a LocationResult."""
    service = AsyncMock()
    service.get_user_location = AsyncMock(
        return_value=LocationResult(
            lat=21.0285,
            lng=105.8542,
            source="mock_data",
            confidence=0.5,
            city="Hà Nội - Hoàn Kiếm",
        )
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def gps_location_service():
    """LocationService that resolves via GPS headers."""
    service = AsyncMock()
    service.get_user_location = AsyncMock(
        return_value=LocationResult(
            lat=10.7769,
            lng=106.7009,
            source="headers",
            confidence=0.95,
            city="Current location",
        )
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def geocoded_location_service():
    """LocationService that resolves via geocoding an address."""
    service = AsyncMock()
    service.get_user_location = AsyncMock(
        return_value=LocationResult(
            lat=35.6762,
            lng=139.6503,
            source="geocoding",
            confidence=0.99,
            city="Tokyo, Japan",
        )
    )
    service.close = AsyncMock()
    return service


@pytest.fixture
def react_agent():
    """ReActAgent with no tools (handlers tested in isolation)."""
    return ReActAgent(tools=[])


@pytest.fixture
def base_state() -> AgentState:
    """Minimal agent state with user/session IDs."""
    return AgentState(
        user_id="u01",
        session_id="test-session",
        user_message="Tìm quán ăn gần đây",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestToolDefinition
# ─────────────────────────────────────────────────────────────────────────────


class TestToolDefinition:
    """Unit tests for the get_user_location JSON schema."""

    def test_user_id_is_required(self):
        """The schema's required list must include user_id."""
        defn = _get_location_tool_def()
        params = defn["function"]["parameters"]
        assert "required" in params
        assert "user_id" in params["required"]

    def test_address_is_optional(self):
        """The address field must not appear in required list."""
        defn = _get_location_tool_def()
        params = defn["function"]["parameters"]
        required = params.get("required", [])
        assert "address" not in required, (
            "address must NOT be in required fields; it is an optional parameter"
        )

    def test_address_has_string_type(self):
        """address, when present, must be typed as string."""
        defn = _get_location_tool_def()
        props = defn["function"]["parameters"]["properties"]
        assert "address" in props
        assert props["address"]["type"] == "string"

    def test_tool_definition_valid_json(self):
        """The whole definition must be JSON-serializable (valid LiteLLM format)."""
        defn = _get_location_tool_def()
        # Should not raise
        json_str = json.dumps(defn)
        parsed = json.loads(json_str)
        assert parsed["type"] == "function"
        assert "function" in parsed
        assert "name" in parsed["function"]
        assert "parameters" in parsed["function"]


# ─────────────────────────────────────────────────────────────────────────────
# TestReActAgentLocationHandler
# ─────────────────────────────────────────────────────────────────────────────


class TestReActAgentLocationHandler:
    """Tests for ReActAgent._tool_get_user_location."""

    @pytest.mark.asyncio
    async def test_returns_lat_lng_json(self, react_agent, mock_location_service, base_state):
        """Handler returns a valid JSON string with lat and lng keys."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            result_str = await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        result = json.loads(result_str)
        assert "lat" in result
        assert "lng" in result
        assert isinstance(result["lat"], (int, float))
        assert isinstance(result["lng"], (int, float))

    @pytest.mark.asyncio
    async def test_uses_location_service(self, react_agent, mock_location_service, base_state):
        """Handler must call LocationService.get_user_location exactly once."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        mock_location_service.get_user_location.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_user_id_and_address(self, react_agent, mock_location_service, base_state):
        """user_id and address args are forwarded to LocationService."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u99", "address": "123 Lê Lợi, Hà Nội"},
                state=base_state,
            )

        mock_location_service.get_user_location.assert_called_once()
        call_kwargs = mock_location_service.get_user_location.call_args.kwargs
        assert call_kwargs["user_id"] == "u99"
        assert call_kwargs["address"] == "123 Lê Lợi, Hà Nội"

    @pytest.mark.asyncio
    async def test_sets_state_location(self, react_agent, mock_location_service, base_state):
        """After calling, state['location'] must be a dict with lat/lng."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        assert "location" in base_state
        assert "lat" in base_state["location"]
        assert "lng" in base_state["location"]

    @pytest.mark.asyncio
    async def test_address_none_not_passed(self, react_agent, mock_location_service, base_state):
        """When address is absent from args, None is passed (not an empty string)."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        call_kwargs = mock_location_service.get_user_location.call_args.kwargs
        assert call_kwargs.get("address") is None

    @pytest.mark.asyncio
    async def test_closes_service(self, react_agent, mock_location_service, base_state):
        """LocationService.close() must be called after the request."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        mock_location_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_called_on_error(self, react_agent, mock_location_service, base_state):
        """close() is still called when get_user_location raises an exception."""
        mock_location_service.get_user_location = AsyncMock(
            side_effect=RuntimeError("geocoding failed")
        )

        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            with pytest.raises(RuntimeError):
                await react_agent._tool_get_user_location(
                    args={"user_id": "u01"},
                    state=base_state,
                )

        mock_location_service.close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# TestFullIntegration
# ─────────────────────────────────────────────────────────────────────────────


class TestFullIntegration:
    """Integration-style tests covering the full location resolution flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_gps_headers(self, react_agent, gps_location_service, base_state):
        """Valid X-User-Lat/X-User-Lng headers → location resolved from headers."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=gps_location_service,
        ):
            result_str = await react_agent._tool_get_user_location(
                args={"user_id": "u01", "address": None},
                state=base_state,
            )

        gps_location_service.get_user_location.assert_called_once()
        call_kwargs = gps_location_service.get_user_location.call_args.kwargs
        assert call_kwargs["user_id"] == "u01"
        assert call_kwargs["address"] is None

        result = json.loads(result_str)
        assert result["lat"] == 10.7769
        assert result["lng"] == 106.7009

    @pytest.mark.asyncio
    async def test_full_flow_fallback_to_mock(
        self, react_agent, mock_location_service, base_state
    ):
        """No headers, no address → falls back to mock data for the user_id."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            result_str = await react_agent._tool_get_user_location(
                args={"user_id": "u01", "address": None},
                state=base_state,
            )

        mock_location_service.get_user_location.assert_called_once()
        call_kwargs = mock_location_service.get_user_location.call_args.kwargs
        assert call_kwargs["user_id"] == "u01"
        assert call_kwargs["address"] is None

        result = json.loads(result_str)
        # Mock returns u01's coordinates (Hà Nội)
        assert result["lat"] == 21.0285
        assert result["lng"] == 105.8542

    @pytest.mark.asyncio
    async def test_full_flow_with_address(self, react_agent, geocoded_location_service, base_state):
        """With an address arg, geocoded_location_service is invoked."""
        with patch(
            "app.services.location_service.LocationService",
            return_value=geocoded_location_service,
        ):
            result_str = await react_agent._tool_get_user_location(
                args={
                    "user_id": "u99",
                    "address": "123 Lê Lợi, Hoàn Kiếm, Hà Nội",
                },
                state=base_state,
            )

        geocoded_location_service.get_user_location.assert_called_once()
        call_kwargs = geocoded_location_service.get_user_location.call_args.kwargs
        assert call_kwargs["user_id"] == "u99"
        assert call_kwargs["address"] == "123 Lê Lợi, Hoàn Kiếm, Hà Nội"

        result = json.loads(result_str)
        assert result["lat"] == 35.6762
        assert result["lng"] == 139.6503

    @pytest.mark.asyncio
    async def test_handler_preserves_state_keys(self, react_agent, mock_location_service, base_state):
        """Other state keys must not be overwritten by the location call."""
        base_state["keyword"] = "phở"
        base_state["radius"] = 3000

        with patch(
            "app.services.location_service.LocationService",
            return_value=mock_location_service,
        ):
            await react_agent._tool_get_user_location(
                args={"user_id": "u01"},
                state=base_state,
            )

        assert base_state.get("keyword") == "phở"
        assert base_state.get("radius") == 3000
        # location key is added, not replacing unrelated keys
        assert base_state["location"]["lat"] == 21.0285
