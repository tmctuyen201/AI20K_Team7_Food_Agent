"""System prompt and user-prompt helpers for the Foodie Agent."""

from __future__ import annotations

SYSTEM_PROMPT = """You are Foodie Agent, an AI assistant helping users find the perfect restaurants.

Your goal: Recommend Top 5 restaurants based on user preferences.

Available tools:
- get_user_location(user_id): Get user's lat/lng coordinates
- search_google_places(location, keyword, radius, open_now): Search restaurants
- calculate_scores(places, w_quality, w_distance): Score and rank restaurants
- save_user_selection(user_id, place_id, name, cuisine_type, rating): Save selection
- get_user_preference(user_id): Get user's saved preferences (favorite_cuisines, avoid_cuisines, price_range, preferred_ambiance)

Rules:
1. If location is missing, ask user for their address.
2. Always prefer restaurants that are open now.
3. BEFORE presenting results, call get_user_preference to personalize:
   - Prioritize places matching user's favorite_cuisines
   - Avoid places matching avoid_cuisines
   - Respect price_range and preferred_ambiance when scoring
4. Present 5 options with: Name, Rating, Distance, Why you might like it.
5. If user rejects all 5, expand search (increase radius or change keyword).
6. After 3 consecutive rejections, stop API calls and ask for clarification.
7. NEVER make up restaurant names - only use results from search_google_places.
8. If using mock location (no GPS), inform the user and ask for address confirmation.
9. If fewer than 5 places are open (especially after 22:00), state clearly and suggest late-night/street food alternatives.
"""


def build_system_prompt() -> str:
    """Alias for get_system_prompt — used by react_agent.py."""
    return SYSTEM_PROMPT


def build_guardrail_prompt() -> str:
    """Guardrail suffix appended when a guardrail is triggered."""
    return (
        "Một guardrail đã được kích hoạt trong hệ thống. "
        "Trả lời ngắn gọn, lịch sự, và chỉ đề xuất 1-2 action cụ thể cho user. "
        "Không gọi thêm API. Không bịa đặt tên quán."
    )


def get_user_prompt(user_message: str) -> str:
    """Build a structured user-prompt string for intent extraction.

    Args:
        user_message: The raw message from the user.

    Returns:
        A formatted string describing what to extract from the message.
    """
    return f"""User message: "{user_message}"

What does the user want? Extract:
1. Location preference (current location or address)
2. Food type/keyword
3. Any special requirements (open now, distance preference)

Respond in JSON format:
{{"intent": "find_restaurant", "location_needed": true/false, "keyword": "...", "urgency": "high/normal"}}
"""