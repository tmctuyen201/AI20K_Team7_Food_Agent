"""Tool registry — maps tool names to BaseTool instances."""

from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool
from app.tools.location_tool import location_tool
from app.tools.google_search_tool import google_search_tool
from app.tools.scoring_tool import scoring_tool
from app.tools.memory_tool import memory_tool
from app.tools.preference_tool import preference_tool

TOOLS: dict[str, BaseTool] = {
    "get_user_location": location_tool,
    "search_google_places": google_search_tool,
    "calculate_scores": scoring_tool,
    "save_user_selection": memory_tool,
    "get_user_preference": preference_tool,
}


def get_tool_registry() -> dict[str, BaseTool]:
    """Return the full tool registry."""
    return TOOLS


def get_tool(name: str) -> BaseTool | None:
    """Return a single tool by name, or None if not found."""
    return TOOLS.get(name)
