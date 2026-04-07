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
                               "Returns location data including lat, lng, and city name. "
                               "If GPS headers are unavailable and no address is provided, "
                               "returns mock data for a sample user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Unique user identifier",
                        },
                        "address": {
                            "type": "string",
                            "description": (
                                "Optional. Text address to geocode (e.g. "
                                "'123 Lê Lợi, Hoàn Kiếm, Hà Nội'). "
                                "If provided, the address is converted to lat/lng "
                                "via the Geocoding API instead of using mock data."
                            ),
                        },
                    },
                    "required": ["user_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_places_api",
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
                "description": "Tính điểm và xếp hạng danh sách quán ăn dựa trên chất lượng và khoảng cách. "
                               "Gợi ý: Tăng w_distance (0.7-0.9) nếu khách hàng đang đói/vội. "
                               "Tăng w_quality (0.7-0.9) nếu khách hàng muốn tìm chỗ ngon nhất.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "places": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Danh sách các quán ăn thu được từ Search Places API",
                        },
                        "w_quality": {
                            "type": "number",
                            "description": "Trọng số chất lượng (0.0 - 1.0). Mặc định: 0.6",
                        },
                        "w_distance": {
                            "type": "number",
                            "description": "Trọng số khoảng cách (0.0 - 1.0). Mặc định: 0.4",
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
                "description": (
                    "Save a restaurant selection when user chooses a restaurant. "
                    "Stores selection in history and updates user preferences. "
                    "Required: user_id, place_id, name. Optional: cuisine_type, rating."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "Unique user identifier",
                        },
                        "place_id": {
                            "type": "string",
                            "description": "Google Places ID of the restaurant",
                        },
                        "name": {
                            "type": "string",
                            "description": "Restaurant name (must be a real place from Google)",
                        },
                        "cuisine_type": {
                            "type": "string",
                            "description": "Type of cuisine (e.g. 'phở', 'bún bò', 'cơm tấm')",
                        },
                        "rating": {
                            "type": "number",
                            "description": "Rating from 0.0 to 5.0",
                            "minimum": 0.0,
                            "maximum": 5.0,
                        },
                    },
                    "required": ["user_id", "place_id", "name"],
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