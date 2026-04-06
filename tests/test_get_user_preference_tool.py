"""Test suite for get_user_preference — service + handler.

Covers:
- Tool schema correctness in app/tools/definitions.py
- ReActAgent._tool_get_user_preference via app/services/history
- Full end-to-end resolution flows
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.agent.react_agent import ReActAgent
from app.agent.state import AgentState
from app.tools.definitions import get_tool_definitions


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_preference_tool_def() -> dict:
    """Return the get_user_preference tool definition dict."""
    tools = get_tool_definitions()
    return next(
        t for t in tools
        if t["function"]["name"] == "get_user_preference"
    )


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_preference() -> dict:
    """Full preference object returned from the store."""
    return {
        "user_id": "u01",
        "favorite_cuisines": ["phở", "bún bò"],
        "avoid_cuisines": ["hải sản"],
        "price_range": "mid",
        "preferred_ambiance": "vỉa hè",
    }


@pytest.fixture
def empty_preference() -> dict:
    """Preference with only default fields."""
    return {
        "user_id": "u99",
        "favorite_cuisines": [],
        "avoid_cuisines": [],
        "price_range": "mid",
        "preferred_ambiance": None,
    }


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
        user_message="Món yêu thích của tôi là gì?",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TestToolDefinition
# ─────────────────────────────────────────────────────────────────────────────


class TestToolDefinition:
    """Unit tests for the get_user_preference JSON schema."""

    def test_user_id_is_required(self):
        """The schema's required list must include user_id."""
        defn = _get_preference_tool_def()
        params = defn["function"]["parameters"]
        assert "required" in params
        assert "user_id" in params["required"]

    def test_user_id_is_string_type(self):
        """user_id parameter must be typed as string."""
        defn = _get_preference_tool_def()
        props = defn["function"]["parameters"]["properties"]
        assert "user_id" in props
        assert props["user_id"]["type"] == "string"

    def test_tool_definition_valid_json(self):
        """The whole definition must be JSON-serializable (valid LiteLLM format)."""
        defn = _get_preference_tool_def()
        # Should not raise
        json_str = json.dumps(defn)
        parsed = json.loads(json_str)
        assert parsed["type"] == "function"
        assert "function" in parsed
        assert "name" in parsed["function"]
        assert "parameters" in parsed["function"]

    def test_get_user_preference_in_definitions(self):
        """get_user_preference must appear in the full tool list."""
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "get_user_preference" in tool_names

    def test_tool_has_no_required_optional_params(self):
        """Only user_id is required; no other params are defined."""
        defn = _get_preference_tool_def()
        params = defn["function"]["parameters"]
        required = params.get("required", [])
        assert required == ["user_id"]
        # No additional required fields
        assert len(required) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TestReActAgentPreferenceHandler
# ─────────────────────────────────────────────────────────────────────────────


class TestReActAgentPreferenceHandler:
    """Tests for ReActAgent._tool_get_user_preference."""

    @pytest.mark.asyncio
    async def test_returns_valid_json(self, react_agent, sample_preference, base_state):
        """Handler must return a valid JSON string."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=sample_preference,
        ):
            result_str = await react_agent._tool_get_user_preference(
                args={"user_id": "u01"},
                state=base_state,
            )

        result = json.loads(result_str)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_returns_full_preference_fields(
        self, react_agent, sample_preference, base_state
    ):
        """Handler must forward all preference fields correctly."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=sample_preference,
        ):
            result_str = await react_agent._tool_get_user_preference(
                args={"user_id": "u01"},
                state=base_state,
            )

        result = json.loads(result_str)
        assert result["user_id"] == "u01"
        assert result["favorite_cuisines"] == ["phở", "bún bò"]
        assert result["avoid_cuisines"] == ["hải sản"]
        assert result["price_range"] == "mid"
        assert result["preferred_ambiance"] == "vỉa hè"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_preference(
        self, react_agent, base_state
    ):
        """When get_user_preference returns empty, handler returns {}."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value={},
        ):
            result_str = await react_agent._tool_get_user_preference(
                args={"user_id": "u99"},
                state=base_state,
            )

        result = json.loads(result_str)
        assert result == {}

    @pytest.mark.asyncio
    async def test_uses_user_id_from_args_first(self, react_agent, sample_preference, base_state):
        """Handler should use user_id from args before falling back to state."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = sample_preference
            await react_agent._tool_get_user_preference(
                args={"user_id": "u05"},
                state=base_state,
            )

            mock_get.assert_called_once_with("u05")

    @pytest.mark.asyncio
    async def test_falls_back_to_state_user_id(self, react_agent, sample_preference):
        """When args.user_id is missing, handler falls back to state.user_id."""
        state: AgentState = {"user_id": "u03"}

        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = sample_preference
            await react_agent._tool_get_user_preference(
                args={},
                state=state,
            )

            mock_get.assert_called_once_with("u03")

    @pytest.mark.asyncio
    async def test_falls_back_to_empty_string_when_no_user_id(self, react_agent):
        """When both args and state are missing user_id, use empty string."""
        state: AgentState = {}

        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = {}
            await react_agent._tool_get_user_preference(
                args={},
                state=state,
            )

            mock_get.assert_called_once_with("")


# ─────────────────────────────────────────────────────────────────────────────
# TestFullIntegration
# ─────────────────────────────────────────────────────────────────────────────


class TestFullIntegration:
    """Integration-style tests covering the full preference resolution flow."""

    @pytest.mark.asyncio
    async def test_preference_found_flow(
        self, react_agent, sample_preference, base_state
    ):
        """Full flow: user has preference → _execute_tool returns it."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=sample_preference,
        ):
            tool_result = await react_agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "u01"}',
                },
                base_state,
            )

        result = json.loads(tool_result)
        assert result["favorite_cuisines"] == ["phở", "bún bò"]

        # State should record the tool call
        assert len(base_state["tool_calls"]) == 1
        assert base_state["tool_calls"][0]["tool"] == "get_user_preference"

    @pytest.mark.asyncio
    async def test_preference_not_found_flow(self, react_agent, base_state):
        """Full flow: user has no preference → returns empty dict."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value={},
        ):
            tool_result = await react_agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "new_user"}',
                },
                base_state,
            )

        result = json.loads(tool_result)
        assert result == {}

    @pytest.mark.asyncio
    async def test_tool_call_error_handled(self, react_agent, base_state):
        """DB error during tool call should be caught and logged."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            side_effect=Exception("JSON store error"),
        ):
            tool_result = await react_agent._execute_tool(
                {
                    "name": "get_user_preference",
                    "arguments": '{"user_id": "u01"}',
                },
                base_state,
            )

        assert "Error:" in tool_result
        assert base_state["tool_calls"][0]["error"] is not None

    @pytest.mark.asyncio
    async def test_routes_to_correct_handler(self, react_agent, sample_preference, base_state):
        """_route_tool must dispatch to _tool_get_user_preference."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=sample_preference,
        ):
            result = await react_agent._route_tool(
                "get_user_preference",
                {"user_id": "u01"},
                base_state,
            )

        parsed = json.loads(result)
        assert "user_id" in parsed

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, react_agent):
        """Unknown tool name should return error string."""
        result = await react_agent._route_tool(
            "nonexistent_tool",
            {},
            {},
        )
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_partial_preference_returned(
        self, react_agent, base_state
    ):
        """Partial preference should only include present fields."""
        partial = {
            "user_id": "u07",
            "favorite_cuisines": ["bánh mì"],
        }

        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=partial,
        ):
            result_str = await react_agent._tool_get_user_preference(
                args={"user_id": "u07"},
                state=base_state,
            )

        result = json.loads(result_str)
        assert result["user_id"] == "u07"
        assert result["favorite_cuisines"] == ["bánh mì"]
        # Absent fields should not appear
        assert "price_range" not in result

    @pytest.mark.asyncio
    async def test_tool_call_start_logged(self, react_agent, sample_preference, base_state):
        """_execute_tool must log tool_call_start with correct tool name."""
        with patch(
            "app.services.history.get_user_preference",
            new_callable=AsyncMock,
            return_value=sample_preference,
        ):
            with patch("app.agent.react_agent.tool_logger") as mock_logger:
                await react_agent._execute_tool(
                    {
                        "name": "get_user_preference",
                        "arguments": '{"user_id": "u01"}',
                    },
                    base_state,
                )

                mock_logger.info.assert_called()
                call_args = str(mock_logger.info.call_args)
                assert "get_user_preference" in call_args