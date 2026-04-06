"""LiteLLM tool definitions for the Foodie Agent."""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("foodie.tool_definitions")


def get_tool_definitions() -> list[dict]:
    """Return LiteLLM-compatible tool definitions.

    These match the system prompt's tool names.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "get_user_location",
                "description": "Get the current latitude and longitude for a user. "
                               "Returns location data including lat, lng, and city name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Unique user identifier",
                        },
                    },
                    "required": ["user_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_google_places",
                "description": "Search Google Places API for restaurants near a location. "
                               "Returns a list of places with basic info.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "object",
                            "description": "Location dict with lat/lng",
                        },
                        "keyword": {
                            "type": "string",
                            "description": "Search keyword (e.g. 'phở', 'cơm tấm')",
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["prominence", "distance"],
                            "description": "How to rank results",
                        },
                        "radius": {
                            "type": "integer",
                            "description": "Search radius in meters",
                        },
                        "open_now": {
                            "type": "boolean",
                            "description": "Only return places open now",
                        },
                    },
                    "required": ["keyword"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_scores",
                "description": "Score and rank a list of places by quality and distance. "
                               "Returns top 5 sorted places.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "places": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of place objects from Google Places API",
                        },
                        "weight_quality": {
                            "type": "number",
                            "description": "Weight for rating (0.0 - 1.0). Default: 0.6",
                        },
                        "weight_distance": {
                            "type": "number",
                            "description": "Weight for proximity (0.0 - 1.0). Default: 0.4",
                        },
                    },
                    "required": ["places"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_user_selection",
                "description": "Save a restaurant selection to user's history.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Unique user identifier",
                        },
                        "place_id": {
                            "type": "string",
                            "description": "Google place ID of the selected restaurant",
                        },
                        "place": {
                            "type": "object",
                            "description": "Full place object to save",
                        },
                    },
                    "required": ["user_id", "place"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_user_preference",
                "description": "Get saved preferences for a user (favorite cuisines, price range, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Unique user identifier",
                        },
                    },
                    "required": ["user_id"],
                },
            },
        },
    ]