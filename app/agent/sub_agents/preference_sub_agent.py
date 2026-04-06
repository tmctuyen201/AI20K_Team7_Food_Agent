"""Preference Sub-Agent — handles user preference queries and updates.

Uses JSON file store (Phase 1).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("foodie.sub_agent.preference")


# ── Pydantic models ─────────────────────────────────────────────────────────────

class PreferenceQueryInput(BaseModel):
    user_id: str = Field(description="User ID")


class PreferenceQueryResult(BaseModel):
    user_id: str
    favorite_cuisines: list[str]
    avoid_cuisines: list[str]
    price_range: str
    preferred_ambiance: str | None
    total_selections: int = 0


# ── Prompt template ──────────────────────────────────────────────────────────────

PREFERENCE_PROMPT = """Bạn là Preference Agent — chuyên gia về sở thích ăn uống của user.

## Nhiệm vụ
Trả lời câu hỏi về sở thích của user hoặc cập nhật sở thích khi user cung cấp thông tin mới.

## Available Tools
1. `get_user_preference(user_id)` — lấy sở thích hiện tại của user
2. `add_favorite_cuisine(user_id, cuisine)` — thêm món ăn yêu thích
3. `remove_favorite_cuisine(user_id, cuisine)` — xóa món ăn khỏi danh sách yêu thích

## Luật
1. Luôn gọi get_user_preference trước khi trả lời về sở thích
2. Nếu user nói "tôi thích ăn X" → gọi add_favorite_cuisine
3. Nếu user nói "tôi không thích X" → gọi remove_favorite_cuisine và thêm vào avoid_cuisines
4. Trả lời tự nhiên, không đọc lệnh

## Ví dụ tương tác
- User: "Tôi hay ăn phở và bún bò"
  → add_favorite_cuisine với cả hai
  → "Đã ghi nhận! Bạn thích phở và bún bò 🍜"

- User: "Tôi không ăn đồ cay"
  → add_favorite_cuisine với avoid_cuisines
  → "OK, mình sẽ không gợi ý đồ cay cho bạn nhé 🌶️"

- User: "Món yêu thích của tôi là gì?"
  → get_user_preference
  → Trả lời dựa trên kết quả
"""


class PreferenceSubAgent:
    """Sub-agent for user preference management.

    Handles queries about preferences and updates when user provides new info.
    """

    def __init__(
        self,
        prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ):
        self.prompt = prompt or PREFERENCE_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens

    def get_system_prompt(self) -> str:
        return self.prompt

    def should_act(self, user_message: str, current_intent: str | None) -> bool:
        """Determine if this sub-agent should handle the message.

        Preference-related intents and keywords.
        """
        preference_keywords = [
            "sở thích", "thích ăn", "không thích",
            "yêu thích", "thường ăn", "hay ăn",
            "món yêu", "món ghét", "món không thích",
            "dị ứng", "kiêng", "không ăn",
            "budget", "ngân sách", "giá",
            "ambiance", "không khí", "phong cách quán",
        ]
        msg_lower = user_message.lower()

        for kw in preference_keywords:
            if kw in msg_lower:
                return True

        if current_intent in ("preference", "favorite", "avoid"):
            return True

        return False

    def build_llm_messages(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.prompt}]
        if conversation_history:
            for msg in conversation_history[-3:]:
                messages.append(msg)
        messages.append({"role": "user", "content": user_message})
        return messages

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_user_preference",
                    "description": "Get current food preferences for a user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User identifier",
                            },
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_favorite_cuisine",
                    "description": "Add a cuisine to user's favorite list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User identifier",
                            },
                            "cuisine": {
                                "type": "string",
                                "description": "Cuisine name (e.g. 'phở', 'bún bò')",
                            },
                        },
                        "required": ["user_id", "cuisine"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "remove_favorite_cuisine",
                    "description": "Remove a cuisine from user's favorite list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User identifier",
                            },
                            "cuisine": {
                                "type": "string",
                                "description": "Cuisine name to remove",
                            },
                        },
                        "required": ["user_id", "cuisine"],
                    },
                },
            },
        ]
