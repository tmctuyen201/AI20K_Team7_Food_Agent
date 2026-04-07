"""Agent runner — wraps LangGraph agent and ReAct agent with LLM response generation.

Supports three agent versions:
  v1        — ReAct-style loop (react_agent.ReActAgent)
  v2        — LangGraph pipeline (nodes.py + graph.py)
  no-tools  — LLM-only, no function calls (nodes.run_no_tools)

The runner is primarily consumed by the WebSocket handler in app/api/chat.py,
which streams step events and LLM tokens back to the client.

For compare=True, all three versions are run in parallel and the combined
result is yielded as a single {"type": "compare_result", ...} event.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Callable, Optional

from app.agent.nodes import (
    parse_intent,
    get_location,
    get_preference,
    search_places,
    score_places,
    run_no_tools,
)
from app.agent.react_agent import ReActAgent
from app.agent.state import AgentState
from app.tools.definitions import get_tool_definitions
from app.db.models import ScoredPlace
from app.core.logging import (
    get_agent_logger,
    get_agent_step_logger,
    log_agent_step,
    log_tool_result,
)
from app.services.llm import llm_client

agent_logger = get_agent_logger()


def _inject_guardrail_state(
    state: AgentState,
    guardrail_result,  # GuardrailResult — imported lazily to avoid circular import
    step_callback: Callable | None,
) -> AgentState:
    """Set guardrail fields on state and log via step callback."""
    state["guardrail_triggered"] = guardrail_result.name
    state["guardrail_message"] = guardrail_result.message
    state["is_complete"] = True

    if step_callback:
        step_callback(
            {
                "type": "reasoning",
                "step": 99,
                "text": f"Guardrail triggered: {guardrail_result.name} — {guardrail_result.message}",
                "tool": None,
            }
        )

    return state


class AgentRunner:
    """Wrapper around all agent versions with LLM-powered responses."""

    def __init__(
        self,
        user_id: str,
        session_id: str,
        model: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.model = model
        self._final_places: list[ScoredPlace] = []
        self._rejection_count: int = 0

    # ── Public API ───────────────────────────────────────────────────────────────

    async def run_async(
        self,
        user_message: str,
        version: str = "v2",
        compare: bool = False,
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        agent_logger.info(
            "[AGENT] run_async called",
            user_message=user_message[:50],
            version=version,
            session_id=self.session_id,
            user_id=self.user_id,
        )
        """Run the selected agent version and stream step + token events.

        Args:
            user_message: The user's chat message.
            version: One of "v1" (ReAct), "v2" (LangGraph), "no-tools" (LLM-only).
            compare: If True, run all three versions and yield a single
                      ``compare_result`` event after all complete.
            model: Per-call LLM model override. Takes precedence over the
                    model set at construction time (``self.model``).
            history: Prior conversation turns to prepend (list of {role, content}).

        Yields:
            dict events:
              - {"type": "reasoning", "step": int, "text": str, "tool": str|None}
              - {"type": "tool_result", "tool": str, "result": dict, "error": str|None}
              - {"type": "token", "data": str}         ← LLM token

              - {"type": "compare_result", "versions": {...}}
        """
        # Per-call override takes precedence over the instance-level model
        effective_model = model if model is not None else self.model

        if compare:
            async for event in self.run_compare(
                user_message, model=effective_model, history=history
            ):
                yield event
            return

        if version == "v1":
            async for event in self._run_v1(
                user_message, effective_model, history=history
            ):
                yield event
        elif version == "v2":
            async for event in self._run_v2(
                user_message, effective_model, history=history
            ):
                yield event
        elif version == "no-tools":
            async for event in self._run_no_tools(
                user_message, effective_model, history=history
            ):
                yield event
        else:
            agent_logger.warning(
                "unknown_agent_version",
                version=version,
                user_id=self.user_id,
                session_id=self.session_id,
            )
            yield {
                "type": "reasoning",
                "step": 1,
                "text": f"Unknown agent version: {version}. Falling back to v2.",
                "tool": None,
            }
            async for event in self._run_v2(
                user_message, effective_model, history=history
            ):
                yield event

    async def run_compare(
        self,
        user_message: str,
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Run all three agent versions in parallel and yield a compare result.

        Yields a single ``{"type": "compare_result", "versions": {...}}`` event
        after all versions have completed.
        """
        yield {
            "type": "reasoning",
            "step": 1,
            "text": "Starting 3-way comparison (v1, v2, no-tools)...",
            "tool": None,
        }

        effective_model = model if model is not None else self.model

        # Run all three in parallel
        v1_coro = self._run_v1(user_message, effective_model, history=history)
        v2_coro = self._run_v2(user_message, effective_model, history=history)
        no_tools_coro = self._run_no_tools(
            user_message, effective_model, history=history
        )

        results: dict[str, dict] = {}

        # Gather in a shield so cancellation doesn't leave dangling tasks
        gathered = await asyncio.shield(
            asyncio.gather(
                _collect_version("v1", v1_coro, results),
                _collect_version("v2", v2_coro, results),
                _collect_version("no-tools", no_tools_coro, results),
            )
        )

        # Build compare result — one entry per version
        compare_payload: dict[str, dict] = {}
        for name, result in gathered:
            evs = result.get("events", [])
            final_text = result.get("final_text", "")

            reasoning_steps = [e for e in evs if e.get("type") == "reasoning"]
            tool_results = [e for e in evs if e.get("type") == "tool_result"]
            # Extract places from the last token / reasoning event if present
            places: list = []

            compare_payload[name] = {
                "text": final_text,
                "places": places,
                "reasoning_steps": reasoning_steps,
                "tool_results": tool_results,
            }

        yield {
            "type": "compare_result",
            "versions": compare_payload,
        }

    # ── Version-specific runners ────────────────────────────────────────────────

    async def _run_v1(
        self,
        user_message: str,
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """ReAct-style agent with streaming step events."""
        agent_logger.info(
            "runner_run_v1_start",
            user_id=self.user_id,
            session_id=self.session_id,
            message_preview=user_message[:100],
        )

        # Build ReAct state
        state: AgentState = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "user_message": user_message,
            "intent": None,
            "location": None,
            "keyword": None,
            "places": [],
            "scored_places": [],
            "shown_place_ids": [],
            "rejection_count": 0,
            "next_page_token": None,
            "last_radius": 2000,
            "messages": [],
            "is_complete": False,
        }

        tools = get_tool_definitions()
        react_agent = ReActAgent(tools=tools)

        reasoning_events: list[dict] = []
        tool_result_events: list[dict] = []

        # Stream step events from ReAct loop
        async for ev in react_agent.run_streaming(
            state, self.user_id, self.session_id, model
        ):
            reasoning_events.append(ev) if ev.get(
                "type") == "reasoning" else None
            tool_result_events.append(ev) if ev.get(
                "type") == "tool_result" else None
            yield ev

        # ── Backup guardrail check after ReAct loop ───────────────────────────
        from app.core.guardrail import check_guardrails

        # Sync places_raw from the nested mutable list that tool calls append to
        raw_list = state.get("places_raw")
        if raw_list and not state.get("places_raw_flat"):
            state["places_raw_flat"] = raw_list
        elif state.get("places_raw_flat") and not raw_list:
            state["places_raw"] = state["places_raw_flat"]

        guardrail_result = check_guardrails(state)
        if guardrail_result.triggered:
            agent_logger.info(
                "runner_guardrail_triggered",
                guardrail=guardrail_result.name,
                user_id=self.user_id,
                session_id=self.session_id,
            )
            # Yield guardrail message as final token
            for chunk in guardrail_result.message:
                yield {"type": "token", "data": chunk}
            yield {"type": "final_text", "text": guardrail_result.message}
            return

        # Build places context from state and stream LLM response
        scored_places: list[ScoredPlace] = []
        if state.get("scored_places"):
            scored_places = state["scored_places"]
        elif state.get("places_scored"):
            scored_places = [ScoredPlace(**p)
                             for p in state["places_scored"][:5]]

        self._final_places = scored_places
        places_context = self._build_places_context(scored_places)

        agent_logger.info(
            "runner_run_v1_places_ready",
            user_id=self.user_id,
            session_id=self.session_id,
            places_count=len(scored_places),
        )

        # Stream LLM tokens
        final_text = ""
        async for token in llm_client.generate_response(
            user_message, places_context, model=model, history=history
        ):
            final_text += token
            yield {"type": "token", "data": token}

        # Emit final_text so run_compare can collect it
        yield {"type": "final_text", "text": final_text}

        agent_logger.info(
            "runner_run_v1_complete",
            user_id=self.user_id,
            session_id=self.session_id,
            places_count=len(scored_places),
        )

        yield {"type": "done", "data": {"places": scored_places}}

    async def _run_v2(
        self,
        user_message: str,
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """LangGraph pipeline with streaming step events via step callbacks."""
        import sys as _sys

        print(f"[!!!] _run_v2 ENTRY user_message={user_message}", flush=True)
        _sys.stdout.flush()
        from queue import Queue, Empty
        from threading import Event as ThreadEvent

        agent_logger.info(
            "runner_run_v2_start",
            user_id=self.user_id,
            session_id=self.session_id,
            message_preview=user_message[:100],
        )

        # Reset shared step counter (safe: single-user session)
        import app.agent.nodes as nodes_module

        nodes_module._graph_step_counter = 0

        step_logger = get_agent_step_logger(self.session_id)

        # Thread-safe queue passes events from executor thread → async consumer
        event_queue: Queue[dict] = Queue()
        # Signals that the graph run is fully done
        graph_done = ThreadEvent()

        def step_callback(event: dict) -> None:
            """Called synchronously by nodes (in executor thread)."""
            ev_type = event.get("type", "reasoning")
            if ev_type == "reasoning":
                log_agent_step(
                    step_logger,
                    step=event.get("step", 0),
                    phase="node",
                    model=model or "default",
                    version="v2",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    message=event.get("text", ""),
                )
            elif ev_type == "tool_result":
                log_tool_result(
                    step_logger,
                    step=event.get("step", 0),
                    tool=event.get("tool", ""),
                    places_count=None,
                    error=None,
                    user_id=self.user_id,
                    session_id=self.session_id,
                )
            # Put in queue (thread-safe); the async consumer drains it
            event_queue.put(event)

        def run_graph_blocking() -> AgentState:
            """Run the agent pipeline manually with proper step callbacks."""
            try:
                initial_state: AgentState = {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "user_message": user_message,
                    "intent": None,
                    "location": None,
                    "keyword": None,
                    "places": [],
                    "scored_places": [],
                    "shown_place_ids": [],
                    "rejection_count": self._rejection_count,
                    "next_page_token": None,
                    "last_radius": 2000,
                    "messages": [],
                    "is_complete": False,
                    "search_done": False,
                    "preferences": None,
                }

                state = initial_state

                # Manual node execution with proper step callbacks
                from app.agent.nodes import (
                    parse_intent,
                    get_location,
                    get_preference,
                    search_places,
                    score_places,
                )

                # Parse intent
                state = parse_intent(state, step_callback)

                # Non-food intent (e.g. "hello") — skip location/search, go straight to LLM
                if state.get("intent") is None:
                    state["is_complete"] = True
                    state["messages"].append(
                        "run_graph_blocking: intent=None, skipped location/search"
                    )
                    graph_done.set()
                    return state

                # Get location
                state = get_location(state, step_callback)

                # Guardrail check after location
                from app.core.guardrail import check_guardrails

                guardrail_after_location = check_guardrails(state)
                if guardrail_after_location.triggered:
                    state["guardrail_triggered"] = guardrail_after_location.name
                    state["guardrail_message"] = guardrail_after_location.message
                    state["is_complete"] = True
                    state = _inject_guardrail_state(
                        state, guardrail_after_location, step_callback
                    )
                    graph_done.set()
                    return state

                # Get preferences
                state = get_preference(state, step_callback)

                # Search places
                state = search_places(state, step_callback)

                # Guardrail check after search
                guardrail_after_scoring = check_guardrails(state)
                if guardrail_after_scoring.triggered:
                    state["guardrail_triggered"] = guardrail_after_scoring.name
                    state["guardrail_message"] = guardrail_after_scoring.message
                    state["is_complete"] = True
                    state = _inject_guardrail_state(
                        state, guardrail_after_scoring, step_callback
                    )
                    graph_done.set()
                    return state

                # Score places
                state = score_places(state, step_callback)

                graph_done.set()
                return state

                # Load user preferences before searching (personalization)
                state = get_preference(state, step_callback=step_callback)

                # Search + score — guardrail (zero / midnight) runs after
                state = search_places(state, step_callback=step_callback)
                state = score_places(state, step_callback=step_callback)

                # ── Guardrail: zero-results / midnight AFTER search has run ─────────
                guardrail_after_scoring = check_guardrails(state)
                if guardrail_after_scoring.triggered:
                    state["guardrail_triggered"] = guardrail_after_scoring.name
                    state["guardrail_message"] = guardrail_after_scoring.message
                    state["is_complete"] = True
                    state = _inject_guardrail_state(
                        state, guardrail_after_scoring, step_callback
                    )

                graph_done.set()
                return state
            except Exception:
                graph_done.set()
                raise

        # Start graph run in thread pool
        loop = asyncio.get_running_loop()
        graph_future = loop.run_in_executor(None, run_graph_blocking)

        # Drain the event queue as events arrive, yielding them immediately
        pending = True
        while pending:
            try:
                event = event_queue.get(timeout=0.05)
                yield event
            except Empty:
                # Check if graph has finished AND queue is drained
                if graph_done.is_set() and event_queue.empty():
                    pending = False
                else:
                    # Check if the future raised an exception
                    if graph_future.done():
                        try:
                            graph_future.result()
                        except Exception as e:
                            agent_logger.error(
                                "graph_run_error",
                                user_id=self.user_id,
                                session_id=self.session_id,
                                error=str(e),
                            )
                            pending = False
                        else:
                            pending = False

        # Get the final state
        try:
            result_state = await graph_future
        except Exception as e:
            agent_logger.error(
                "graph_run_error",
                user_id=self.user_id,
                session_id=self.session_id,
                error=str(e),
            )
            return

        # Extract scored places
        scored_places: list[ScoredPlace] = result_state.get(
            "scored_places") or []

        # ── Check if guardrail was triggered ─────────────────────────────────
        if result_state.get("guardrail_triggered"):
            guardrail_msg = result_state.get("guardrail_message", "")
            agent_logger.info(
                "runner_v2_guardrail_triggered",
                guardrail=result_state["guardrail_triggered"],
                user_id=self.user_id,
                session_id=self.session_id,
            )
            # _inject_guardrail_state already yielded step-99 via the callback
            # (visible to the frontend as a reasoning event), so only stream
            # the message as a token here — do NOT yield it twice.
            for chunk in guardrail_msg:
                yield {"type": "token", "data": chunk}
            yield {"type": "final_text", "text": guardrail_msg}
            yield {"type": "done", "data": {"places": []}}
            return

        # Log node messages
        for msg in result_state.get("messages") or []:
            agent_logger.debug("node_log", node_message=msg)

        intent = result_state.get("intent")
        scored_places: list[ScoredPlace] = result_state.get(
            "scored_places") or []

        self._final_places = scored_places

        # Determine places context based on results
        if scored_places:
            # Success: we have places to show
            places_context = self._build_places_context(scored_places)
            agent_logger.info(
                "runner_run_v2_places_ready",
                user_id=self.user_id,
                session_id=self.session_id,
                places_count=len(scored_places),
            )
        elif intent == "find_restaurant":
            # Food query but no places found - provide empty context
            places_context = ""
            agent_logger.info(
                "runner_v2_no_places_found",
                intent=intent,
                user_id=self.user_id,
                session_id=self.session_id,
            )
        else:
            # Non-food intent or general conversation
            places_context = ""
            agent_logger.info(
                "runner_v2_non_food_intent",
                intent=intent,
                user_id=self.user_id,
                session_id=self.session_id,
            )

        # Stream LLM response (only called once now)
        final_text = ""
        async for token in llm_client.generate_response(
            user_message, places_context, model=model, history=history
        ):
            final_text += token
            yield {"type": "token", "data": token}

        yield {"type": "final_text", "text": final_text}

        # Log the final assistant response
        step_logger = get_agent_step_logger(self.session_id)
        log_agent_step(
            step_logger,
            step=5,  # After scoring step
            phase="response",
            model=model or "unknown",
            version="v2",
            user_id=self.user_id,
            session_id=self.session_id,
            # Truncate for logging
            message=f"[Final Response] {final_text[:500]}",
        )

        agent_logger.info(
            "runner_run_v2_complete",
            user_id=self.user_id,
            session_id=self.session_id,
            places_count=len(scored_places),
        )

        yield {"type": "done", "data": {"places": scored_places}}

    async def _run_no_tools(
        self,
        user_message: str,
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """LLM-only version — no tool calls."""
        effective_model = model or self.model or "default"
        agent_logger.info(
            "runner_run_no_tools_start",
            user_id=self.user_id,
            session_id=self.session_id,
            model=effective_model,
            message_preview=user_message[:100],
        )

        # Collect reasoning steps from run_no_tools, then stream real LLM tokens
        async for ev in run_no_tools(
            user_message=user_message,
            user_id=self.user_id,
            session_id=self.session_id,
            model=effective_model,
        ):
            if ev.get("type") == "final_response":
                # run_no_tools generated a quick response; now stream the real one
                continue
            yield ev

        # Stream the full LLM response as tokens
        final_text = ""
        async for token in llm_client.generate_response(
            user_message, places_context="", model=effective_model, history=history
        ):
            final_text += token
            yield {"type": "token", "data": token}

        yield {"type": "final_text", "text": final_text}

        agent_logger.info(
            "runner_run_no_tools_complete",
            user_id=self.user_id,
            session_id=self.session_id,
        )

        yield {"type": "done", "data": {"places": []}}

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _build_places_context(self, places: list[ScoredPlace]) -> str:
        """Build context string from places for LLM."""
        if not places:
            return ""

        lines = []
        for i, place in enumerate(places[:5], 1):
            lines.append(f"{i}. {place.name}")
            lines.append(f"   - Rating: {place.rating}/5 sao")
            lines.append(f"   - Khoảng cách: {place.distance_km:.1f} km")
            if place.cuisine_type:
                lines.append(f"   - Loại món: {place.cuisine_type}")
            if place.address:
                lines.append(f"   - Địa chỉ: {place.address}")
            if place.open_now:
                lines.append("   - Đang mở cửa")
            lines.append("")

        return "\n".join(lines)

    def get_final_places(self) -> list[ScoredPlace]:
        """Return the scored places from the last agent run."""
        return self._final_places

    def handle_rejection(self) -> Optional[str]:
        """Handle when user rejects all suggestions."""
        self._rejection_count += 1

        if self._rejection_count >= 3:
            agent_logger.warning(
                "rejection_max_reached",
                user_id=self.user_id,
                session_id=self.session_id,
                rejection_count=self._rejection_count,
            )
            return (
                "Bạn đã từ chối nhiều gợi ý liên tiếp. "
                "Bạn có thể cho tôi biết thêm về ngân sách, "
                "loại quán mong muốn hoặc khu vực cụ thể không?"
            )

        agent_logger.info(
            "rejection_handled",
            user_id=self.user_id,
            session_id=self.session_id,
            rejection_count=self._rejection_count,
        )
        return None

    def reset_rejection_count(self) -> None:
        """Reset the rejection counter after a successful selection."""
        self._rejection_count = 0


# ── Helper for run_compare ──────────────────────────────────────────────────────


async def _collect_version(
    name: str,
    coro: AsyncGenerator,
    results: dict,
) -> tuple[str, dict]:
    """Collect all events from a version coroutine into results[name]."""
    events = []
    final_text = ""
    async for ev in coro:
        events.append(ev)
        if ev.get("type") == "final_text":
            final_text = ev.get("text", "")
    results[name] = {"events": events, "final_text": final_text}
    return name, results[name]
