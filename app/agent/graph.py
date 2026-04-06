"""LangGraph StateGraph builder for the Foodie Agent."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.agent.nodes import (
    parse_intent,
    get_location,
    search_places,
    score_places,
    should_continue,
)


def create_agent_graph():
    """Build and compile the LangGraph agent.

    The graph has a single linear pass::

        parse_intent → get_location → search_places → score_places → END

    The ``should_continue`` function is defined for future extension
    (e.g. branching on rejection to expand the search).
    """
    graph = StateGraph(AgentState)

    # ── Nodes ──────────────────────────────────────────────────────────────────
    graph.add_node("parse_intent", parse_intent)
    graph.add_node("get_location", get_location)
    graph.add_node("search_places", search_places)
    graph.add_node("score_places", score_places)

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.set_entry_point("parse_intent")

    graph.add_edge("parse_intent", "get_location")
    graph.add_edge("get_location", "search_places")
    graph.add_edge("search_places", "score_places")
    graph.add_edge("score_places", END)

    return graph.compile()
