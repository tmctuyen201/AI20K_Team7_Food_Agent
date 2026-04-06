"""LLM integration using LiteLLM for multi-provider support."""

from __future__ import annotations

import os
from typing import AsyncGenerator

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("foodie.llm")

SYSTEM_PROMPT = """Bạn là Foodie Agent - trợ lý AI giúp người dùng tìm quán ăn ngon.

Khi có danh sách quán ăn, hãy trả lời bằng tiếng Việt, giới thiệu các quán một cách tự nhiên và hấp dẫn.
Mỗi quán cần có: tên, rating (sao), khoảng cách, và 1-2 dòng giới thiệu ngắn gọn.

Nếu không tìm được quán nào, xin lỗi và hỏi thêm thông tin."""


def _resolve_model(provider: str, model: str) -> str:
    """Map internal model name to provider-prefixed LiteLLM format."""
    if "/" in model:
        return model
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        return f"openai/{model}"
    if model.startswith("claude-"):
        return f"anthropic/{model}"
    return model


class LLMClient:
    """Unified LLM client supporting Anthropic, OpenAI, and mock fallback."""

    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = self._get_api_key()
        self._litellm = None

    def _get_api_key(self) -> str:
        if self.provider == "anthropic":
            return settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        return settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")

    def _get_model(self) -> str:
        return _resolve_model(self.provider, self.model)

    def _litellm_completion(self):
        """Lazily load the sync completion function (safe: called in run_in_executor)."""
        if self._litellm is None:
            try:
                from litellm import completion
                self._litellm = completion
            except ImportError:
                logger.warning("litellm not installed, LLM calls will be mocked")
                self._litellm = False
        return self._litellm

    async def generate_response(
        self,
        user_message: str,
        places_context: str,
    ) -> AsyncGenerator[str, None]:
        """Generate a natural language response about restaurant recommendations.

        Yields:
            Token strings for streaming response.
        """
        completion_fn = self._litellm_completion()

        if not completion_fn or not self.api_key:
            # Fallback: yield mock response
            async for chunk in self._mock_response(places_context):
                yield chunk
            return

        try:
            user_prompt = f"""Người dùng hỏi: "{user_message}"

Danh sách quán tìm được:
{places_context}

Hãy giới thiệu các quán này một cách tự nhiên bằng tiếng Việt."""

            response = completion_fn(
                model=self._get_model(),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                api_key=self.api_key,
                stream=True,
                max_tokens=500,
            )

            # LiteLLM stream=True returns a synchronous generator (not async)
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        except Exception as e:
            logger.error("llm_error", error=str(e))
            async for chunk in self._mock_response(places_context):
                yield chunk

    async def generate_response_simple(
        self,
        user_message: str,
        places_context: str,
    ) -> str:
        """Non-streaming version - returns full response as string."""
        chunks = []
        async for chunk in self.generate_response(user_message, places_context):
            chunks.append(chunk)
        return "".join(chunks)

    async def _mock_response(self, places_context: str) -> AsyncGenerator[str, None]:
        """Fallback mock response when no API key is available."""
        if not places_context or places_context.strip() == "":
            yield "Xin lỗi, tôi không tìm thấy quán phù hợp. Bạn có thể cho tôi biết thêm địa chỉ không?"
            return

        yield "Tôi đã tìm được Top 5 quán ăn cho bạn:\n\n"

        lines = places_context.strip().split("\n")
        for line in lines:
            if line.strip():
                yield line + "\n"

        yield "\n\nBạn muốn chọn quán nào?"


# Global singleton
llm_client = LLMClient()
