"""LangGraph agent state definition."""

from __future__ import annotations

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
