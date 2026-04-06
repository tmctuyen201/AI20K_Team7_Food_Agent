"""ReAct Agent — core loop with full logging."""

from __future__ import annotations

import time
from typing import Any

from app.agent.prompt import build_system_prompt, build_guardrail_prompt
from app.agent.state import AgentState, ToolCall
from app.core.logging import get_agent_logger, get_llm_logger, get_tool_logger

agent_logger = get_agent_logger()
llm_logger = get_llm_logger()
tool_logger = get_tool_logger()


class ReActAgent:
    """ReAct-based agent for finding restaurants.

    The agent runs a Thought → Action → Observation loop
    using an LLM to decide which tools to call.
    """

    def __init__(self, tools: list[dict[str, Any]]):
        """Initialize the agent.

        Args:
            tools: LiteLLM-compatible tool definitions.
        """
        self.tools = tools
        self.max_iterations = 10

    async def run(self, state: AgentState) -> AgentState:
        """Run the ReAct loop until completion or max iterations.

        Args:
            state: Initial agent state.

        Returns:
            Updated agent state with final_response and is_done=True.
        """
        agent_logger.info(
            "agent_run_start",
            user_id=state.get("user_id"),
            session_id=state.get("session_id"),
            user_message=state.get("user_message", "")[:100],
        )

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            state["iteration"] = iteration

            agent_logger.info(
                "agent_iteration_start",
                iteration=iteration,
                user_id=state.get("user_id"),
            )

            # Build messages for this turn
            messages = self._build_messages(state)

            # Call LLM with tools
            response = await self._call_llm(messages)

            # Check for tool calls in response
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # No tool call → agent gave final answer
                final_text = self._extract_text(response)
                state["final_response"] = final_text
                state["is_done"] = True
                agent_logger.info(
                    "agent_run_done",
                    user_id=state.get("user_id"),
                    iterations=iteration,
                    final_response_preview=final_text[:200] if final_text else "",
                )
                break

            # Execute each tool call
            for tc in tool_calls:
                result = await self._execute_tool(tc, state)
                # Append tool result as assistant message
                messages.append({
                    "role": "assistant",
                    "content": str(tc),
                })
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {result}",
                })

            # Check guardrail
            if state.get("guardrail_triggered"):
                guardrail_msg = state.get("guardrail_message", "")
                state["final_response"] = guardrail_msg
                state["is_done"] = True
                agent_logger.warning(
                    "agent_guardrail_triggered",
                    guardrail=state["guardrail_triggered"],
                    user_id=state.get("user_id"),
                    iteration=iteration,
                )
                break

            if state.get("is_done"):
                break

        if iteration >= self.max_iterations:
            agent_logger.warning(
                "agent_max_iterations_reached",
                user_id=state.get("user_id"),
                iterations=iteration,
            )
            state["final_response"] = "Tôi đang gặp khó khăn để tìm quán phù hợp. Bạn có thể mô tả rõ hơn không?"
            state["is_done"] = True

        return state

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _build_messages(self, state: AgentState) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": build_system_prompt()}]

        if state.get("guardrail_triggered"):
            messages.append({
                "role": "system",
                "content": build_guardrail_prompt(),
            })

        # History of tool calls for context
        tool_calls = state.get("tool_calls", [])
        if tool_calls:
            history = "\n".join(
                f"- {tc['tool']}: {tc.get('args', {}), tc.get('result', '')}"
                for tc in tool_calls
            )
            messages.append({
                "role": "system",
                "content": f"Previous tool calls this session:\n{history}",
            })

        messages.append({
            "role": "user",
            "content": state.get("user_message", ""),
        })

        return messages

    async def _call_llm(self, messages: list[dict[str, str]]) -> Any:
        from app.core.provider import llm_chat

        llm_logger.info(
            "llm_call_start",
            message_count=len(messages),
            has_tools=bool(self.tools),
        )

        start = time.monotonic()
        try:
            response = await llm_chat(
                messages=messages,
                tools=self.tools,
                stream=False,
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            llm_logger.info(
                "llm_call_completed",
                elapsed_ms=round(elapsed_ms, 1),
                has_tool_calls=bool(self._extract_tool_calls(response)),
            )
            return response

        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            llm_logger.error(
                "llm_call_error",
                error=str(e),
                elapsed_ms=round(elapsed_ms, 1),
            )
            raise

    def _extract_tool_calls(self, response: Any) -> list[dict]:
        try:
            choices = getattr(response, "choices", []) or []
            delta = choices[0].delta if choices else None
            tool_calls = getattr(delta, "tool_calls", None) or []
            return [
                {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in tool_calls
            ]
        except Exception:
            return []

    def _extract_text(self, response: Any) -> str:
        try:
            choices = getattr(response, "choices", []) or []
            msg = choices[0].message if choices else None
            return getattr(msg, "content", "") or ""
        except Exception:
            return ""

    async def _execute_tool(
        self,
        tool_call: dict,
        state: AgentState,
    ) -> str:
        """Execute a tool call and log the result."""
        from app.core.provider import llm_chat_sync

        tool_name = tool_call.get("name", "")
        raw_args = tool_call.get("arguments", "{}")

        tool_logger.info(
            "tool_call_start",
            tool=tool_name,
            arguments=raw_args[:500],
            session_id=state.get("session_id"),
        )

        start = time.monotonic()
        error = None
        result = ""

        try:
            # Parse arguments
            import json
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

            # Route to the appropriate tool handler
            result = await self._route_tool(tool_name, args, state)

            duration_ms = (time.monotonic() - start) * 1000

            tool_logger.info(
                "tool_call_success",
                tool=tool_name,
                duration_ms=round(duration_ms, 1),
                result_preview=str(result)[:200],
            )

        except Exception as e:
            error = str(e)
            duration_ms = (time.monotonic() - start) * 1000
            result = f"Error: {error}"

            tool_logger.error(
                "tool_call_error",
                tool=tool_name,
                error=error,
                duration_ms=round(duration_ms, 1),
            )

        # Record in state
        tc_entry = {
            "tool": tool_name,
            "args": args if "args" in locals() else {},
            "result": result,
            "error": error,
        }
        state.setdefault("tool_calls", []).append(tc_entry)

        return result

    async def _route_tool(
        self,
        tool_name: str,
        args: dict,
        state: AgentState,
    ) -> str:
        """Route to the correct tool handler."""
        import json

        handlers = {
            "get_user_location": self._tool_get_user_location,
            "search_google_places": self._tool_search_google_places,
            "calculate_scores": self._tool_calculate_scores,
            "save_user_selection": self._tool_save_user_selection,
            "get_user_preference": self._tool_get_user_preference,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return f"Unknown tool: {tool_name}"

        return await handler(args, state)

    async def _tool_get_user_location(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Get user location from GPS header, geocoding, or mock data."""
        from app.services.geocoding import geocode_address
        from app.tools.mock_data import get_mock_location

        user_id = args.get("user_id") or state.get("user_id", "")

        # Try GPS header / state
        location = state.get("location")
        if location:
            return json.dumps({"lat": location["lat"], "lng": location["lng"]})

        # Try geocoding (if address was provided)
        # For now, use mock
        mock = get_mock_location(user_id)
        state["location"] = {"lat": mock["lat"], "lng": mock["lng"]}
        return json.dumps({"lat": mock["lat"], "lng": mock["lng"], "city": mock["city"]})

    async def _tool_search_google_places(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Search Google Places API."""
        from app.services.google_places import search_places

        location = state.get("location", {})
        lat = args.get("lat") or location.get("lat")
        lng = args.get("lng") or location.get("lng")
        keyword = args.get("keyword") or state.get("keyword", "restaurant")
        sort_by = args.get("sort_by", "prominence")
        radius = args.get("radius", state.get("radius", 2000))
        open_now = args.get("open_now", state.get("open_now", True))

        results = await search_places(
            lat=lat,
            lng=lng,
            keyword=keyword,
            sort_by=sort_by,
            radius=radius,
            open_now=open_now,
        )

        state["places_raw"] = results
        state["keyword"] = keyword
        state["radius"] = radius

        return json.dumps({"count": len(results), "places": results[:20]})

    async def _tool_calculate_scores(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Score and rank places."""
        from app.tools.scoring import score_places

        places = state.get("places_raw", [])
        w_quality = args.get("weight_quality", 0.6)
        w_distance = args.get("weight_distance", 0.4)

        scored = score_places(places, w_quality, w_distance)
        state["places_scored"] = scored

        return json.dumps({"top_5": scored[:5]})

    async def _tool_save_user_selection(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Save user selection to history."""
        from app.services.history import save_selection

        user_id = args.get("user_id") or state.get("user_id", "")
        place = args.get("place")

        if isinstance(place, str):
            import json
            place = json.loads(place)

        await save_selection(user_id, place)
        return json.dumps({"status": "saved"})

    async def _tool_get_user_preference(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Get user preference from history."""
        from app.services.history import get_user_preference

        user_id = args.get("user_id") or state.get("user_id", "")
        pref = await get_user_preference(user_id)
        return json.dumps(pref or {})