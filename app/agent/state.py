"""ReAct Agent state definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class AgentState(TypedDict, total=False):
    """Shared state across ReAct loop iterations."""

    user_id: str
    session_id: str
    user_message: str
    intent: str | None
    location: dict | None
    headers: dict | None
    keyword: str | None
    sort_by: str
    radius: int
    open_now: bool
    places_raw: list[dict]
    places_scored: list[dict]
    tool_calls: list[dict]
    rejection_count: int
    guardrail_triggered: str | None
    guardrail_message: str | None
    final_response: str | None
    is_done: bool
    next_page_token: str | None
    shown_place_ids: list[str]
    error: str | None


@dataclass
class ToolCall:
    """Represents a single tool invocation for logging."""

    tool_name: str
    arguments: dict
    result: str | None = None
    error: str | None = None
    duration_ms: float | None = None