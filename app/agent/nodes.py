"""LangGraph node functions for the Foodie Agent."""

from __future__ import annotations

from typing import Any

from app.agent.state import AgentState
from app.db.models import LatLng, Place, ScoredPlace
from app.tools.registry import get_tool_registry


def parse_intent(state: AgentState) -> AgentState:
    """Parse user message to extract intent and keyword.

    Simple keyword-based extraction. In a full implementation this would
    be delegated to an LLM call, but we keep it lightweight here.
    """
    user_message = state["user_message"]
    user_id = state["user_id"]

    # Vietnamese and international food keywords
    keywords = [
        "phở", "bún", "cơm", "bánh", "trà", "cà phê",
        "hải sản", "nướng", "lẩu", "burger", "pizza",
        "sushi", "thịt", "gà", "bò", "mì", "cá",
        "cappuccino", "espresso", "trà sữa", "bubble tea",
    ]

    found_keyword: str | None = None
    for kw in keywords:
        if kw.lower() in user_message.lower():
            found_keyword = kw
            break

    # Detect if user is asking for a location-based search
    location_words = ["gần", "near", "đâu", "ở đâu", "tìm", "kiếm", "xung quanh"]
    needs_location = any(w in user_message.lower() for w in location_words)

    state["intent"] = "find_restaurant"
    state["keyword"] = found_keyword or "restaurant"

    state["messages"].append(
        f"parse_intent: intent=find_restaurant keyword={state['keyword']}"
    )

    return state


def get_location(state: AgentState) -> AgentState:
    """Get user location using the tool registry."""
    user_id = state["user_id"]

    registry = get_tool_registry()
    location_tool = registry["get_user_location"]

    result: dict[str, Any] = location_tool._run(user_id=user_id)

    state["location"] = LatLng(lat=result["lat"], lng=result["lng"])
    state["messages"].append(
        f"Got location: {result['lat']}, {result['lng']} (source: {result['source']})"
    )

    return state


def search_places(state: AgentState) -> AgentState:
    """Search for restaurants using Google Places via the tool registry."""
    location = state["location"]
    keyword = state.get("keyword", "restaurant")
    radius = state.get("last_radius", 2000)

    registry = get_tool_registry()
    search_tool = registry["search_google_places"]

    raw_results: list[dict[str, Any]] = search_tool._run(
        location=location,
        keyword=keyword,
        radius=radius,
        open_now=True,
    )

    # Convert raw dicts to Place model objects
    places = [Place(**r) for r in raw_results]
    state["places"] = places

    # Track shown place IDs to avoid duplicates
    existing_ids: set[str] = set(state.get("shown_place_ids", []))
    for place in places:
        existing_ids.add(place.place_id)
    state["shown_place_ids"] = list(existing_ids)

    state["messages"].append(f"search_places: found {len(places)} places")

    return state


def score_places(state: AgentState) -> AgentState:
    """Score and rank places using the tool registry."""
    places = state.get("places", [])
    if not places:
        state["is_complete"] = True
        state["messages"].append("score_places: no places to score")
        return state

    registry = get_tool_registry()
    scoring_tool = registry["calculate_scores"]

    # Pass place dicts (Place.model_dump()) to the scoring tool
    place_dicts = [p.model_dump() for p in places]
    scored_dicts: list[dict[str, Any]] = scoring_tool._run(
        places=place_dicts,
        w_quality=0.6,
        w_distance=0.4,
    )

    # Convert scored dicts back to ScoredPlace model objects (top 5)
    scored = [ScoredPlace(**d) for d in scored_dicts[:5]]
    state["scored_places"] = scored

    state["messages"].append(f"score_places: top {len(scored)} scored places")

    return state


def should_continue(state: AgentState) -> str:
    """Decide the next step after score_places.

    Returns:
        "end" to finish the graph, or "search" to do another search
        (e.g. when expanding radius on rejection).
    """
    if state.get("is_complete"):
        return "end"
    if not state.get("scored_places"):
        return "search"
    return "end"
