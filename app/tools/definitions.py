"""LiteLLM tool definitions for the Foodie Agent."""

from __future__ import annotations

from sqlalchemy import true

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
                "name": "Search Places API",
                "description": "Tìm kiếm quán ăn qua Google Maps dựa trên tọa độ và từ khóa. Trả về JSON gồm: tên, đánh giá, địa chỉ, khoảng cách và giá cả.",
                "parameters": {
                "type": "object",
                "properties": {
                    "lat": {
                    "type": "number",
                    "description": "Vĩ độ hiện tại của người dùng (Latitude)."
                    },
                    "lng": {
                    "type": "number",
                    "description": "Kinh độ hiện tại của người dùng (Longitude)."
                    },
                    "keyword": {
                    "type": "string",
                    "description": "Từ khóa món ăn hoặc loại quán cần tìm (ví dụ: phở, sushi, pizza)."
                    },
                    "preference": {
                    "type": "string",
                    "enum": ["prominence", "distance"],
                    "default": "prominence",
                    "description": "Ưu tiên: 'prominence' để tìm quán ngon/nổi tiếng, 'distance' để tìm quán gần nhất."
                    }
                },
                "required": ["lat", "lng", "keyword"]
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