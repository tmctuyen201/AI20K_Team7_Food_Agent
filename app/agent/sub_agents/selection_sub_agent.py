"""Selection Sub-Agent — handles saving user restaurant choices.

Uses JSON file store (Phase 1). Prompt is configurable via .env / settings.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

from app.core.logging import get_logger

logger = get_logger("foodie.sub_agent.selection")


# ── Pydantic models ─────────────────────────────────────────────────────────────

class SaveSelectionInput(BaseModel):
    user_id: str = Field(description="User ID")
    place_id: str = Field(description="Google Places ID of the restaurant")
    name: str = Field(description="Restaurant name")
    cuisine_type: str | None = Field(None, description="Type of cuisine (e.g. 'phở', 'bún bò')")
    rating: float = Field(0.0, ge=0.0, le=5.0, description="Rating 0.0 - 5.0")


class SelectionResult(BaseModel):
    success: bool
    message: str
    selection_id: str | None = None
    preference_updated: bool = False


# ── Prompt template (configurable) ──────────────────────────────────────────────

SELECTION_PROMPT = """Bạn là Selection Agent — chuyên gia về lưu lịch sử chọn quán ăn của user.

## Nhiệm vụ
Khi user chọn một quán ăn, bạn gọi tool `save_user_selection` để lưu lại.

## Luật
1. user_id và place_id là bắt buộc
2. name là bắt buộc, phải là tên quán thật từ Google Places
3. cuisine_type: nếu biết thì thêm, không biết thì để None
4. rating: 0.0 - 5.0, mặc định 0.0 nếu không có thông tin
5. Nếu user mô tả món ăn → suy ra cuisine_type (VD: "phở" → "phở")
6. Trả lời ngắn gọn xác nhận đã lưu

## Ví dụ
User: "Tôi chọn quán số 1"
→ Gọi save_user_selection với place_id, name, cuisine_type phù hợp
→ Reply: "Đã lưu [Tên quán] vào lịch sử của bạn! Món {cuisine} nghe hấp dẫn đấy 😄"
"""


# ── Sub-agent class ─────────────────────────────────────────────────────────────

class SelectionSubAgent:
    """Sub-agent responsible for saving user restaurant selections.

    Prompt can be overridden via constructor for testing/prompt engineering.
    """

    def __init__(
        self,
        prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 512,
    ):
        self.prompt = prompt or SELECTION_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens

    def get_system_prompt(self) -> str:
        return self.prompt

    def should_act(self, user_message: str, current_intent: str | None) -> bool:
        """Determine if this sub-agent should handle the message.

        Args:
            user_message: Raw user input.
            current_intent: Detected intent from main agent (if any).

        Returns:
            True if user is selecting/choosing a restaurant.
        """
        selection_keywords = [
            "chọn", "chọn quán", "tôi muốn", "lấy quán",
            "đặt", "quán số", "số", "pick", "choose",
            "lấy", "quán này", "quán đó",
        ]
        msg_lower = user_message.lower().strip()

        # Direct selection keywords
        for kw in selection_keywords:
            if kw in msg_lower:
                return True

        # Intent-based
        if current_intent in ("select", "choose", "pick"):
            return True

        # Number-only selection (e.g. "2", "3")
        if msg_lower.isdigit() and 1 <= int(msg_lower) <= 5:
            return True

        return False

    def build_llm_messages(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """Build messages for the sub-agent LLM call.

        Args:
            user_message: Current user input.
            conversation_history: Optional previous turns.

        Returns:
            Messages ready for LLM chat completion.
        """
        messages = [{"role": "system", "content": self.prompt}]

        if conversation_history:
            # Include last 3 turns for context
            for msg in conversation_history[-3:]:
                messages.append(msg)

        messages.append({"role": "user", "content": user_message})
        return messages

    def parse_result(self, llm_output: str) -> str:
        """Parse LLM output into a user-facing response.

        Args:
            llm_output: Raw LLM text response.

        Returns:
            Cleaned response string for the user.
        """
        return llm_output.strip()

    def get_tool_definitions(self) -> list[dict]:
        """LiteLLM tool definitions for save_user_selection."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "save_user_selection",
                    "description": (
                        "Save a restaurant selection when user chooses a restaurant. "
                        "This stores the selection in history and updates user preferences."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User identifier",
                            },
                            "place_id": {
                                "type": "string",
                                "description": "Google Places ID of the restaurant",
                            },
                            "name": {
                                "type": "string",
                                "description": "Restaurant name",
                            },
                            "cuisine_type": {
                                "type": "string",
                                "description": "Type of cuisine (e.g. 'phở', 'bún bò')",
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
            }
        ]
