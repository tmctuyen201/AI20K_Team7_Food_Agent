"""LangGraph node functions for the Foodie Agent."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Callable

from app.agent.state import AgentState
from app.db.models import LatLng, Place, ScoredPlace
from app.tools.registry import get_tool_registry

# Step counter shared across nodes for a single graph run
_graph_step_counter: int = 0


def _next_step() -> int:
    global _graph_step_counter
    _graph_step_counter += 1
    return _graph_step_counter


def parse_intent(
    state: AgentState,
    step_callback: Callable | None = None,
) -> AgentState:
    """Parse user message to extract intent and keyword.

    Returns None intent when no food-related keyword is found (LLM gen will be skipped).
    Detects "select" intent when user chooses a restaurant.
    """
    step = _next_step()
    user_message = state["user_message"].lower().strip()
    user_id = state["user_id"]

    if step_callback:
        step_callback({
            "type": "reasoning",
            "step": step,
            "text": f"[Step {step}] Parsing intent from: {user_message[:80]}",
            "tool": None,
        })

    # Vietnamese and international food keywords
    food_keywords = [
        "phở", "bún", "cơm", "bánh", "trà", "cà phê",
        "hải sản", "nướng", "lẩu", "burger", "pizza",
        "sushi", "thịt", "gà", "bò", "mì", "cá",
        "cappuccino", "espresso", "trà sữa", "bubble tea",
        "đồ ăn", "quán", "nhà hàng", "ăn", "uống",
    ]

    # Selection / confirmation keywords
    select_keywords = [
        "chọn", "tôi chọn", "em chọn", "mình chọn",
        "lấy quán", "đặt", "book", "reserve",
    ]

    # 1. Detect "select" intent first
    if any(kw in user_message for kw in select_keywords):
        state["intent"] = "select"
        state["keyword"] = None
        state["is_complete"] = True
        state["messages"].append("parse_intent: intent=select (user chose a restaurant)")
        if step_callback:
            step_callback({
                "type": "reasoning",
                "step": step,
                "text": f"[Step {step}] Intent detected: select (user chose a restaurant)",
                "tool": None,
            })
        return state

    # 2. Detect food keyword
    found_keyword: str | None = None
    for kw in food_keywords:
        if kw in user_message:
            found_keyword = kw
            break

    if found_keyword:
        state["intent"] = "find_restaurant"
        state["keyword"] = found_keyword
        state["messages"].append(
            f"parse_intent: intent=find_restaurant keyword={found_keyword}"
        )
        if step_callback:
            step_callback({
                "type": "reasoning",
                "step": step,
                "text": f"[Step {step}] Intent detected: find_restaurant (keyword={found_keyword})",
                "tool": None,
            })
    else:
        # No food keyword → still run through the pipeline (no search)
        # but LLM will respond naturally as a friendly food agent
        state["intent"] = None
        state["keyword"] = None
        state["is_complete"] = True
        state["messages"].append("parse_intent: intent=None (not food-related)")
        if step_callback:
            step_callback({
                "type": "reasoning",
                "step": step,
                "text": f"[Step {step}] Intent detected: None (not food-related)",
                "tool": None,
            })

    return state


def get_location(
    state: AgentState,
    step_callback: Callable | None = None,
) -> AgentState:
    """Get user location using the tool registry."""
    step = _next_step()
    user_id = state["user_id"]

    if step_callback:
        step_callback({
            "type": "reasoning",
            "step": step,
            "text": f"[Step {step}] Getting user location...",
            "tool": "get_user_location",
        })

    registry = get_tool_registry()
    location_tool = registry["get_user_location"]

    result: dict[str, Any] = location_tool._run(user_id=user_id)

    state["location"] = LatLng(lat=result["lat"], lng=result["lng"])
    state["messages"].append(
        f"Got location: {result['lat']}, {result['lng']} (source: {result['source']})"
    )

    if step_callback:
        step_callback({
            "type": "tool_result",
            "tool": "get_user_location",
            "result": {"lat": result["lat"], "lng": result["lng"], "source": result["source"]},
            "error": None,
        })

    return state


def search_places(
    state: AgentState,
    step_callback: Callable | None = None,
) -> AgentState:
    """Search for restaurants using Google Places via the tool registry.

    Skipped entirely when intent is None (off-topic message) or "select".
    """
    step = _next_step()

    if step_callback:
        step_callback({
            "type": "reasoning",
            "step": step,
            "text": f"[Step {step}] Searching Google Places...",
            "tool": "search_google_places",
        })

    # Skip search for non-food messages or selection confirmations
    if state.get("intent") not in ("find_restaurant",):
        state["is_complete"] = True
        state["places"] = []
        state["scored_places"] = []
        state["messages"].append("search_places: skipped (intent not find_restaurant)")
        if step_callback:
            step_callback({
                "type": "tool_result",
                "tool": "search_google_places",
                "result": {"count": 0, "skipped": True},
                "error": None,
            })
        return state

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

    if step_callback:
        step_callback({
            "type": "tool_result",
            "tool": "search_google_places",
            "result": {"count": len(places)},
            "error": None,
        })

    return state


def score_places(
    state: AgentState,
    step_callback: Callable | None = None,
) -> AgentState:
    """Score and rank places using the tool registry."""
    step = _next_step()
    places = state.get("places", [])

    if step_callback:
        step_callback({
            "type": "reasoning",
            "step": step,
            "text": f"[Step {step}] Scoring {len(places)} places...",
            "tool": "calculate_scores",
        })

    if not places:
        state["is_complete"] = True
        state["messages"].append("score_places: no places to score")
        if step_callback:
            step_callback({
                "type": "tool_result",
                "tool": "calculate_scores",
                "result": {"count": 0},
                "error": None,
            })
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

    if step_callback:
        step_callback({
            "type": "tool_result",
            "tool": "calculate_scores",
            "result": {"count": len(scored)},
            "error": None,
        })

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


# ── No-tools version ────────────────────────────────────────────────────────────

async def run_no_tools(
    user_message: str,
    user_id: str,
    session_id: str,
    model: str,
) -> AsyncGenerator[dict, None]:
    """LLM-only agent — generates a natural response without any tool calls.

    Yields:
        Reasoning step dicts plus final text in a "final_response" key.
    """
    from app.services.llm import LLMClient

    yield {
        "type": "reasoning",
        "step": 1,
        "text": "Generating response (no tools)...",
        "tool": None,
    }

    client = LLMClient(model=model)
    response_text = await client.generate_response_simple(
        user_message=user_message,
        places_context="",
    )

    yield {
        "type": "reasoning",
        "step": 2,
        "text": "Response ready",
        "tool": None,
    }

    # Inject the final text into the yielded dict so the runner can extract it
    yield {"type": "final_response", "text": response_text}
