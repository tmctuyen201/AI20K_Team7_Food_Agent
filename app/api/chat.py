"""WebSocket endpoint for real-time chat with streaming response."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.agent.runner import AgentRunner
from app.core.auth import verify_token
from app.core.logging import get_logger
from app.db.models import ScoredPlace
from app.tools.registry import get_tool_registry

router = APIRouter()
logger = get_logger("foodie.api.chat")


# ── Chat history writer (JSON store) ────────────────────────────────────────────


class ChatHistoryWriter:
    """Appends user/assistant messages to the JSON chat_history store."""

    def __init__(self) -> None:
        from app.db.connection import chat_history_store

        self._store = chat_history_store
        # Accumulators: session_id → {"user": str, "assistant": list[str]}
        self._accumulators: dict[str, dict[str, Any]] = {}

    def start_turn(self, session_id: str, user_message: str) -> None:
        """Call before sending user message to agent."""
        logger.info(
            "[CHAT_HISTORY] start_turn called",
            session_id=session_id,
            user_message_length=len(user_message),
            total_accumulators_before=len(self._accumulators),
        )
        self._accumulators[session_id] = {
            "user": user_message,
            "user_ts": datetime.now(timezone.utc).isoformat(),
            "assistant_parts": [],
            "assistant_ts": None,
        }
        logger.info(
            "[CHAT_HISTORY] start_turn completed",
            session_id=session_id,
            total_accumulators_after=len(self._accumulators),
        )

    def append_assistant_chunk(self, session_id: str, token: str) -> None:
        """Append a streaming token to the assistant accumulator."""
        acc = self._accumulators.get(session_id)
        if acc is not None:
            acc["assistant_parts"].append(token)
            logger.debug(
                "[CHAT_HISTORY] append_chunk",
                session_id=session_id,
                token_length=len(token),
                total_chunks=len(acc["assistant_parts"]),
            )

    def commit_turn(self, session_id: str) -> None:
        """Flush the accumulated turn to the JSON store on `done` event."""
        logger.info(
            "[CHAT_HISTORY] commit_turn START",
            session_id=session_id,
            accumulator_count=len(self._accumulators),
            has_accumulator=session_id in self._accumulators,
        )

        acc = self._accumulators.pop(session_id, None)
        if acc is None:
            logger.warning("[CHAT_HISTORY] no_accumulator found", session_id=session_id)
            return

        logger.info(
            "[CHAT_HISTORY] accumulator details",
            session_id=session_id,
            user_length=len(acc.get("user", "")),
            assistant_parts_count=len(acc.get("assistant_parts", [])),
        )

        user_content = acc["user"].strip()
        assistant_content = "".join(acc["assistant_parts"]).strip()

        logger.info(
            "chat_history_commit_content",
            session_id=session_id,
            has_user=bool(user_content),
            has_assistant=bool(assistant_content),
        )

        if not user_content:
            logger.warning("chat_history_no_user_content", session_id=session_id)
            return

        try:
            # Load existing session history
            all_sessions = self._store._read()
            if session_id not in all_sessions:
                all_sessions[session_id] = {"messages": []}
                logger.info("chat_history_created_new_session", session_id=session_id)

            messages = all_sessions[session_id]["messages"]

            if user_content:
                messages.append(
                    {
                        "role": "user",
                        "content": user_content,
                        "timestamp": acc["user_ts"],
                    }
                )

            if assistant_content:
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                        "timestamp": acc.get("assistant_ts")
                        or datetime.now(timezone.utc).isoformat(),
                    }
                )

            all_sessions[session_id]["messages"] = messages
            self._store._write(all_sessions)

            logger.info(
                "chat_history_commit_success",
                session_id=session_id,
                total_messages=len(messages),
            )

        except Exception as e:
            logger.error(
                "chat_history_commit_failed", session_id=session_id, error=str(e)
            )


chat_history_writer = ChatHistoryWriter()


def _get_chat_history(session_id: str) -> list[dict]:
    """Read prior user/assistant messages from the JSON history store."""
    from app.db.connection import chat_history_store

    try:
        all_sessions = chat_history_store._read()
        if session_id not in all_sessions:
            all_sessions[session_id] = {"messages": []}
            chat_history_store._write(all_sessions)
        return all_sessions.get(session_id, {}).get("messages", [])
    except Exception:
        return []


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self.active_connections.pop(session_id, None)

    async def send_token(self, session_id: str, token: str) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "token",
                    "data": token,
                }
            )

    async def send_done(self, session_id: str, places: list[ScoredPlace]) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "done",
                    "data": {"places": [p.model_dump() for p in places]},
                }
            )

    async def send_reasoning(
        self,
        session_id: str,
        step: int,
        text: str,
        tool: str | None,
    ) -> None:
        """Send a reasoning step event to the client."""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "reasoning",
                    "step": step,
                    "text": text,
                    "tool": tool,
                }
            )

    async def send_tool_result(
        self,
        session_id: str,
        tool: str,
        result: dict[str, Any],
        error: str | None,
    ) -> None:
        """Send a tool result event to the client."""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "tool_result",
                    "tool": tool,
                    "result": result,
                    "error": error,
                }
            )

    async def send_compare_result(
        self,
        session_id: str,
        versions: dict[str, Any],
    ) -> None:
        """Send a comparison result event to the client."""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "compare_result",
                    "versions": versions,
                }
            )

    async def send_error(self, session_id: str, message: str) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "error",
                    "message": message,
                }
            )

    async def send_success(self, session_id: str, message: str) -> None:
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(
                {
                    "type": "success",
                    "message": message,
                }
            )


manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
    model: str | None = Query(default=None),
    version: str = Query(default="v2"),
    compare: bool = Query(default=False),
) -> None:
    """WebSocket endpoint for chat with streaming response.

    Query params:
        token   (required) — JWT auth token
        model   (optional) — LLM model override, e.g. "gpt-4o-mini"
        version (optional) — agent version: "v1" | "v2" | "no-tools" (default "v2")
        compare (optional) — if "true", run all 3 versions and compare (default "false")

    Message protocol (client → server):
        {"text": "I want Italian food"}          — chat message
        {"text": "...", "model": "...", "version": "...", "compare": true} — with overrides
        {"type": "select_place", "place": {...}}  — user clicked a place card

    Message protocol (server → client):
        {"type": "token",     "data": "..."}              — streaming token chunk
        {"type": "reasoning", "step": N, "text": "...", "tool": null|"tool_name"}
        {"type": "tool_result","tool": "...", "result": {...}, "error": null}
        {"type": "compare_result", "versions": {...}}    — comparison of all 3 versions
        {"type": "done",      "data": {"places": [...]}} — final response + places
        {"type": "success",   "message": "..."}          — action confirmed
        {"type": "error",     "message": "..."}           — error occurred
    """
    session_id = ""
    user_id = ""

    # Normalise compare flag from string "true"/"false" → bool
    compare_enabled = str(compare).lower() in ("true", "1", "yes")

    # Track processed messages to prevent duplicates
    processed_messages: set[str] = set()

    try:
        payload = verify_token(token)
        user_id = str(payload.get("user_id", ""))
        session_id = str(payload.get("session_id", ""))

        if not user_id or not session_id:
            await websocket.send_json(
                {"type": "error", "message": "Invalid token payload"}
            )
            return

        await manager.connect(websocket, session_id)

        while True:
            raw = await websocket.receive_text()
            message: dict[str, Any] = json.loads(raw)
            msg_type = str(message.get("type", "text"))
            logger.info(
                "[WEBSOCKET] received message",
                session_id=session_id,
                msg_type=msg_type,
                raw_length=len(raw),
            )

            # ── select_place: user clicked a restaurant card ─────────────────
            if msg_type == "select_place":
                place_data = message.get("place") or {}
                if not place_data:
                    await manager.send_error(session_id, "Missing place data")
                    continue

                registry = get_tool_registry()
                memory_tool = registry["save_user_selection"]
                result = memory_tool._run(
                    user_id=user_id,
                    place_id=str(place_data.get("place_id", "")),
                    name=str(place_data.get("name", "")),
                    cuisine_type=str(place_data.get("cuisine_type") or ""),
                    rating=float(place_data.get("rating") or 0.0),
                )
                if result.get("success"):
                    await manager.send_success(
                        session_id,
                        f"Đã lưu lựa chọn: {place_data.get('name')} - Cám ơn bạn!",
                    )
                else:
                    await manager.send_error(session_id, "Không lưu được lựa chọn")
                # Clear processed messages after place selection
                logger.info(
                    "[WEBSOCKET] clearing processed_messages after place selection",
                    session_id=session_id,
                    processed_count=len(processed_messages),
                )
                processed_messages.clear()
                continue

            # ── text: normal chat message ─────────────────────────────────────
            user_text = str(message.get("text", "")).strip()
            if not user_text:
                continue

            # Prevent duplicate message processing
            message_key = f"{session_id}:{user_text}"
            logger.info(
                "[BE] checking duplicate",
                session_id=session_id,
                message_key=message_key,
                processed_count=len(processed_messages),
                in_processed=message_key in processed_messages,
            )
            if message_key in processed_messages:
                logger.warning(
                    "[BE] DUPLICATE MESSAGE IGNORED",
                    session_id=session_id,
                    message=user_text[:50],
                )
                continue

            processed_messages.add(message_key)
            logger.info(
                "[BE] added to processed",
                session_id=session_id,
                message_key=message_key,
                processed_count=len(processed_messages),
            )
            logger.info(
                "[BE] chat_message_received - STARTING AGENT",
                session_id=session_id,
                user_id=user_id,
                message=user_text[:50],
                timestamp=datetime.now().isoformat(),
            )

            # Merge query-param defaults with per-message overrides
            resolved_model: str | None = (
                str(message["model"]).strip() or model
                if message.get("model") not in (None, "")
                else model
            )
            resolved_version = (
                str(message["version"]).strip() or version
                if message.get("version") not in (None, "")
                else version
            )
            resolved_compare = (
                str(message.get("compare", "")).lower() in ("true", "1", "yes")
                if "compare" in message
                else compare_enabled
            )

            # Normalise version to one of the known values
            if resolved_version not in ("v1", "v2", "no-tools"):
                resolved_version = "v2"

            # ── Compare mode: run all 3 versions in parallel ──────────────────
            if resolved_compare:
                await manager.send_reasoning(
                    session_id, 0, "Bắt đầu so sánh 3 phiên bản...", None
                )
                history = _get_chat_history(session_id)
                compare_result = await _run_compare(
                    user_message=user_text,
                    model=resolved_model,
                    user_id=user_id,
                    session_id=session_id,
                    history=history,
                )
                await manager.send_compare_result(session_id, compare_result)
                # No places in compare mode (each version manages its own)
                await manager.send_done(session_id, [])
                # Clear processed messages after compare
                logger.info(
                    "[WEBSOCKET] clearing processed_messages after compare",
                    session_id=session_id,
                    processed_count=len(processed_messages),
                )
                processed_messages.clear()
                continue

            # ── Single-version run ────────────────────────────────────────────
            agent_runner = AgentRunner(user_id=user_id, session_id=session_id)
            history = _get_chat_history(session_id)

            # Start accumulating this turn's messages for JSON history
            logger.info(
                "[WEBSOCKET] calling start_turn",
                session_id=session_id,
                user_text=user_text[:50],
            )
            chat_history_writer.start_turn(session_id, user_text)
            logger.info("[WEBSOCKET] start_turn completed", session_id=session_id)

            # Track if we already committed the turn
            turn_committed = False

            async for event in agent_runner.run_async(
                user_text,
                model=resolved_model,
                version=resolved_version,
                history=history,
            ):
                # The runner yields either plain token strings (backward compat) or
                # event dicts for structured messages.
                if isinstance(event, dict):
                    event_type = event.get("type", "")
                    if event_type == "reasoning":
                        await manager.send_reasoning(
                            session_id,
                            step=event.get("step", 0),
                            text=event.get("text", ""),
                            tool=event.get("tool"),
                        )
                    elif event_type == "tool_result":
                        await manager.send_tool_result(
                            session_id,
                            tool=event.get("tool", ""),
                            result=event.get("result", {}),
                            error=event.get("error"),
                        )
                    elif event_type == "token":
                        # Token event from LLM stream — accumulate for JSON history
                        token_data = event.get("data", "")
                        await manager.send_token(session_id, token_data)
                        chat_history_writer.append_assistant_chunk(
                            session_id, token_data
                        )
                    elif event_type == "done":
                        # Done event with places — commit history and send done
                        places = event.get("data", {}).get("places", [])
                        await manager.send_done(session_id, places)
                        chat_history_writer.commit_turn(session_id)
                        turn_committed = True
                    elif event_type == "compare_result":
                        await manager.send_compare_result(
                            session_id,
                            event.get("versions", {}),
                        )
                    # "final_text" events are informational only — no action needed
                else:
                    # Plain token string — backward-compatible token stream
                    token_str = str(event)
                    await manager.send_token(session_id, token_str)
                    chat_history_writer.append_assistant_chunk(session_id, token_str)

            # Commit only if not already committed (for v1 or other versions without "done" event)
            if not turn_committed:
                chat_history_writer.commit_turn(session_id)
                final_places = agent_runner.get_final_places()
                await manager.send_done(session_id, final_places)

    except WebSocketDisconnect:
        # Clear processed messages on disconnect
        logger.info(
            "[WEBSOCKET] clearing processed_messages on disconnect",
            session_id=session_id or "unknown",
            processed_count=len(processed_messages),
        )
        processed_messages.clear()
        manager.disconnect(session_id)
    except json.JSONDecodeError:
        if session_id:
            await manager.send_error(session_id, "Invalid JSON message")
    except Exception as e:
        # Clear processed messages on error
        logger.info(
            "[WEBSOCKET] clearing processed_messages on exception",
            session_id=session_id or "unknown",
            processed_count=len(processed_messages),
            error=str(e),
        )
        processed_messages.clear()
        if session_id:
            await manager.send_error(session_id, str(e))
        manager.disconnect(session_id)


# ── Compare runner ──────────────────────────────────────────────────────────────


async def _run_compare(
    user_message: str,
    model: str | None,
    user_id: str,
    session_id: str,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    """Run all 3 agent versions in parallel and return a compare_result dict.

    The returned shape matches the `compare_result` WS message format:
        {
            "v1":     {"text": "", "places": [...], "reasoning_steps": [...]},
            "v2":     {"text": "", "places": [...], "reasoning_steps": [...]},
            "no-tools": {"text": "", "places": [],   "reasoning_steps": [...]},
        }
    """
    import asyncio

    async def _run_single(version: str) -> dict[str, Any]:
        runner = AgentRunner(user_id=user_id, session_id=f"{session_id}_{version}")
        steps: list[dict[str, Any]] = []
        text_parts: list[str] = []
        places_list: list[dict[str, Any]] = []

        async for event in runner.run_async(
            user_message, model=model, version=version, history=history
        ):
            if isinstance(event, dict):
                etype = event.get("type", "")
                if etype == "reasoning":
                    steps.append(
                        {
                            "step": event.get("step", 0),
                            "text": event.get("text", ""),
                            "tool": event.get("tool"),
                        }
                    )
                elif etype == "tool_result":
                    # Collect places from tool results
                    result_data = event.get("result") or {}
                    if "places" in result_data:
                        places_list.extend(result_data["places"])
                elif etype == "token":
                    text_parts.append(str(event))
            else:
                text_parts.append(str(event))

        return {
            "text": "".join(text_parts),
            "places": places_list,
            "reasoning_steps": steps,
        }

    try:
        v1_result, v2_result, no_tools_result = await asyncio.gather(
            _run_single("v1"),
            _run_single("v2"),
            _run_single("no-tools"),
        )
    except Exception:
        # If parallel execution fails, fall back to sequential
        v1_result = await _run_single("v1")
        v2_result = await _run_single("v2")
        no_tools_result = await _run_single("no-tools")

    return {
        "v1": v1_result,
        "v2": v2_result,
        "no-tools": no_tools_result,
    }
