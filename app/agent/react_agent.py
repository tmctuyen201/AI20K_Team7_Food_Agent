"""ReAct Agent — core loop with full logging."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator

from app.agent.prompt import build_system_prompt, build_guardrail_prompt
from app.agent.state import AgentState, ToolCall
from app.core.guardrail import check_guardrails
from app.core.logging import get_agent_logger, get_llm_logger, get_tool_logger, log_tool_call, log_tool_result, log_agent_step

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

            llm_logger.debug(
                "llm_messages_payload",
                message_count=len(messages),
                messages_preview=[
                    {k: (v[:200] if isinstance(v, str) else v) for k, v in m.items()}
                    for m in messages
                ],
            )

            # Call LLM with tools
            response = await self._call_llm(messages)

            # Check for tool calls in response
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # No tool call → agent gave final answer
                final_text = self._extract_text(response)
                state["final_response"] = final_text
                state["is_done"] = True
                agent_logger.warning(
                    "agent_run_done_no_tool",
                    user_id=state.get("user_id"),
                    iteration=iteration,
                    has_tools=bool(self.tools),
                    final_response_preview=final_text[:300] if final_text else "(empty)",
                    tools=[t["function"]["name"] for t in self.tools],
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

            # ── Guardrail check after each tool-execution iteration ──────────────
            guardrail_result = check_guardrails(state)
            if guardrail_result.triggered:
                state["guardrail_triggered"] = guardrail_result.name
                state["guardrail_message"] = guardrail_result.message
                state["final_response"] = guardrail_result.message
                state["is_done"] = True
                agent_logger.warning(
                    "agent_guardrail_triggered",
                    guardrail=guardrail_result.name,
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

    async def run_streaming(
        self,
        state: AgentState,
        user_id: str,
        session_id: str,
        model: str | None = None,
    ) -> AsyncIterator[dict]:
        """Streaming version of run() that yields step events.

        Yields dicts with:
            - {"type": "reasoning", "step": N, "text": "...", "tool": None|str}
            - {"type": "tool_result", "tool": str, "result": str, "error": None|str}

        The ``stream`` param to ``llm_chat`` stays False (tool calling requires
        non-streaming to read tool_calls cleanly from the full message).
        """
        from app.core.provider import llm_chat
        from app.core.logging import get_agent_step_logger

        step_logger = get_agent_step_logger(session_id)
        effective_model = model or "default"
        version_label = "v1"

        agent_logger.info(
            "agent_run_streaming_start",
            user_id=user_id,
            session_id=session_id,
            user_message=state.get("user_message", "")[:100],
        )

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            state["iteration"] = iteration

            log_agent_step(
                step_logger,
                step=iteration,
                phase="think",
                model=effective_model,
                version=version_label,
                user_id=user_id,
                session_id=session_id,
                message=f"[Step {iteration}] Thinking...",
            )
            yield {
                "type": "reasoning",
                "step": iteration,
                "text": f"[Step {iteration}] Thinking...",
                "tool": None,
            }

            # Build messages for this turn
            messages = self._build_messages(state)

            # Call LLM with tools (no streaming — tool_calls live in full message)
            response = await llm_chat(
                messages=messages,
                tools=self.tools,
                stream=False,
            )

            # Check for tool calls in response
            tool_calls = self._extract_tool_calls(response)

            if not tool_calls:
                # No tool call → agent gave final answer
                final_text = self._extract_text(response)
                state["final_response"] = final_text
                state["is_done"] = True

                log_agent_step(
                    step_logger,
                    step=iteration,
                    phase="final",
                    model=effective_model,
                    version=version_label,
                    user_id=user_id,
                    session_id=session_id,
                    message="Final response ready",
                )
                yield {
                    "type": "reasoning",
                    "step": iteration,
                    "text": "Final response ready",
                    "tool": None,
                }
                return

            # Execute each tool call
            for tc in tool_calls:
                tool_name = tc.get("name", "")

                log_tool_call(
                    step_logger,
                    step=iteration,
                    tool=tool_name,
                    args=tc.get("arguments", "")[:500],
                    user_id=user_id,
                    session_id=session_id,
                )
                yield {
                    "type": "reasoning",
                    "step": iteration,
                    "text": f"Calling {tool_name}...",
                    "tool": tool_name,
                }

                result_str = await self._execute_tool(tc, state)

                log_tool_result(
                    step_logger,
                    step=iteration,
                    tool=tool_name,
                    places_count=None,
                    error=None,
                    user_id=user_id,
                    session_id=session_id,
                )
                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": result_str,
                    "error": None,
                }

                # Append tool result as assistant + user messages for next iteration
                messages.append({
                    "role": "assistant",
                    "content": str(tc),
                })
                messages.append({
                    "role": "user",
                    "content": f"Tool result: {result_str}",
                })

            # ── Guardrail check after each tool-execution iteration ──────────────
            from app.core.guardrail import check_guardrails
            guardrail_result = check_guardrails(state)
            if guardrail_result.triggered:
                state["guardrail_triggered"] = guardrail_result.name
                state["guardrail_message"] = guardrail_result.message
                state["final_response"] = guardrail_result.message
                state["is_done"] = True

                log_agent_step(
                    step_logger,
                    step=iteration,
                    phase="guardrail",
                    model=effective_model,
                    version=version_label,
                    user_id=user_id,
                    session_id=session_id,
                    message=f"Guardrail triggered: {guardrail_result.name}",
                )
                yield {
                    "type": "reasoning",
                    "step": iteration,
                    "text": f"Guardrail triggered: {guardrail_result.name}",
                    "tool": None,
                }
                return

            if state.get("is_done"):
                log_agent_step(
                    step_logger,
                    step=iteration,
                    phase="done",
                    model=effective_model,
                    version=version_label,
                    user_id=user_id,
                    session_id=session_id,
                    message="Final response ready",
                )
                yield {
                    "type": "reasoning",
                    "step": iteration,
                    "text": "Final response ready",
                    "tool": None,
                }
                return

        # Max iterations reached
        agent_logger.warning(
            "agent_max_iterations_reached",
            user_id=user_id,
            iterations=iteration,
        )
        state["final_response"] = "Tôi đang gặp khó khăn để tìm quán phù hợp. Bạn có thể mô tả rõ hơn không?"
        state["is_done"] = True

        log_agent_step(
            step_logger,
            step=iteration,
            phase="max_iterations",
            model=effective_model,
            version=version_label,
            user_id=user_id,
            session_id=session_id,
            message="Max iterations reached",
        )
        yield {
            "type": "reasoning",
            "step": iteration,
            "text": "Final response ready",
            "tool": None,
        }

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

            tool_calls = self._extract_tool_calls(response)
            raw_response = ""
            try:
                choices = getattr(response, "choices", []) or []
                msg = choices[0].message if choices else None
                raw_response = f"content={getattr(msg, 'content', None)!r} tool_calls={getattr(msg, 'tool_calls', None)!r}"
            except Exception as e:
                raw_response = f"parse_error: {e}"
            llm_logger.warning(
                "llm_call_completed",
                elapsed_ms=round(elapsed_ms, 1),
                has_tool_calls=bool(tool_calls),
                tool_names=[tc["name"] for tc in tool_calls] if tool_calls else None,
                response_text_preview=(
                    self._extract_text(response)[:500]
                    if not tool_calls else None
                ),
                raw_response=raw_response,
                system_prompt_preview=messages[0]["content"][:300] if messages else "",
                user_message=messages[-1]["content"] if messages else "",
                tool_count=len(self.tools),
                tool_names_available=[t["function"]["name"] for t in self.tools],
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
            if not choices:
                return []

            # stream=False → tool_calls live in message, not delta
            msg = choices[0].message if choices else None
            if msg is None:
                return []

            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                return [
                    {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                    for tc in tool_calls
                ]

            # Fallback: stream=True delta (first chunk may be partial)
            delta = choices[0].delta if choices else None
            if delta is None:
                return []
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
        from app.core.guardrail import check_guardrails

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
        """Get user location via LocationService (GPS → geocoding → mock)."""
        from app.services.location_service import LocationService

        user_id = str(args.get("user_id") or state.get("user_id", ""))
        address = args.get("address")
        headers = state.get("headers")

        tool_logger.info(
            "tool_get_user_location_start",
            user_id=user_id,
            address=address,
            has_headers=headers is not None,
            headers=headers,
        )

        service = LocationService()
        try:
            result = await service.get_user_location(
                user_id=user_id,
                address=address,
                headers=headers,
            )
            tool_logger.info(
                "tool_get_user_location_result",
                user_id=user_id,
                source=result.source,
                lat=result.lat,
                lng=result.lng,
                confidence=result.confidence,
                city=result.city,
                needs_confirmation=result.needs_confirmation,
            )
        finally:
            await service.close()

        state["location"] = result.to_dict()

        # Track location source for guardrail checks
        state["location_source"] = result.source

        # Build response dict
        response = result.to_dict()

        # Flag ambiguous location in state for guardrail
        if result.needs_confirmation:
            state["ambiguous_location"] = True
            state["location_confidence"] = result.confidence

        # Add warning for mock_data source
        if result.source == "mock_data":
            response["_warning"] = (
                "Mình chưa xác định được vị trí chính xác của bạn. "
                f"Đang dùng vị trí mặc định: {result.city}. "
                "Bạn có thể cho biết địa chỉ hoặc khu vực đang ở không?"
            )

        return json.dumps(response)

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
        """Save user selection to JSON store."""
        import json

        from app.services.history import save_selection

        user_id = str(args.get("user_id") or state.get("user_id", ""))
        place_id = str(args.get("place_id", ""))
        name = str(args.get("name", ""))
        cuisine_type = args.get("cuisine_type")
        rating = float(args.get("rating", 0.0))

        # If the LLM passes a "place" dict instead of flat args, unpack it
        if not name and not place_id:
            place = args.get("place")
            if isinstance(place, str):
                place = json.loads(place)
            if place:
                place_id = str(place.get("place_id", ""))
                name = str(place.get("name", ""))
                cuisine_type = place.get("cuisine_type")
                rating = float(place.get("rating", 0.0))

        result = await save_selection(user_id, {
            "place_id": place_id,
            "name": name,
            "cuisine_type": cuisine_type,
            "rating": rating,
        })
        return json.dumps(result)

    async def _tool_get_user_preference(
        self,
        args: dict,
        state: AgentState,
    ) -> str:
        """Get user preference from JSON store."""
        import json

        from app.services.history import get_user_preference

        user_id = str(args.get("user_id") or state.get("user_id", ""))
        pref = await get_user_preference(user_id)
        return json.dumps(pref)