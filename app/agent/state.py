"""LangGraph agent state definition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict, Optional

from app.db.models import LatLng, Place, ScoredPlace


class AgentState(TypedDict):
    """Shared state passed between LangGraph nodes."""

    user_id: str
    session_id: str
    user_message: str
    intent: Optional[str]
    location: Optional[LatLng]
    keyword: Optional[str]
    places: list[Place]
    scored_places: list[ScoredPlace]
    shown_place_ids: list[str]
    rejection_count: int
    next_page_token: Optional[str]
    last_radius: int
    messages: list[str]
    is_complete: bool


@dataclass
class ToolCall:
    """Represents a single tool invocation for logging."""

    tool_name: str
    arguments: dict
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
