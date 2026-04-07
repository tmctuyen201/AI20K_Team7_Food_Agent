"""LLM integration using LiteLLM for multi-provider support."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("foodie.llm")

SYSTEM_PROMPT = """Bạn là Foodie Agent - trợ lý AI giúp người dùng tìm quán ăn ngon.

Khi có danh sách quán ăn, hãy trả lời bằng tiếng Việt, giới thiệu các quán một cách tự nhiên và hấp dẫn.
Mỗi quán cần có: tên, rating (sao), khoảng cách, và 1-2 dòng giới thiệu ngắn gọn.

Nếu không tìm được quán nào, xin lỗi và hỏi thêm thông tin."""

SYSTEM_PROMPT_GENERAL = """Bạn là Foodie Agent - trợ lý AI thân thiện của ứng dụng tìm quán ăn ngon.

Luôn trả lời bằng tiếng Việt, thân thiện và tự nhiên. Bạn có thể:
- Chào hỏi và trò chuyện thông thường
- Trả lời các câu hỏi về ẩm thực, món ăn
- Gợi ý món ăn, địa điểm ăn uống ngon
- Nếu người dùng hỏi về quán ăn cụ thể, hãy hỏi thêm địa điểm/khu vực để tìm kiếm phù hợp

Giữ câu trả lời ngắn gọn, tự nhiên, có personality."""


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

    def __init__(self, model: str | None = None):
        """Initialize the client.

        Args:
            model: Optional model override (e.g. "gpt-4o-mini"). If not provided,
                   falls back to settings.llm_model.
        """
        self.provider = settings.llm_provider
        self._model_override = model
        self.model = model or settings.llm_model
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
        model: str | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a natural language response about restaurant recommendations.

        Args:
            user_message: The user's message.
            places_context: Context string built from scored places.
            model: Optional model override for this call.
            history: Prior conversation turns to prepend (list of {role, content}).

        Yields:
            Token strings for streaming response.
        """
        resolved_model = model or self.model
        resolved_provider = self.provider
        # Detect provider from model name if overridden
        if model:
            if model.startswith("claude-"):
                resolved_provider = "anthropic"
            elif (
                model.startswith("gpt-")
                or model.startswith("o1")
                or model.startswith("o3")
            ):
                resolved_provider = "openai"
        resolved_model = _resolve_model(resolved_provider, resolved_model)

        # Skip litellm if no API key available
        if not self.api_key:
            async for chunk in self._mock_response(places_context):
                yield chunk
            return

        completion_fn = self._litellm_completion()
        print(completion_fn)
        if not completion_fn:
            async for chunk in self._mock_response(places_context):
                yield chunk
            print("No completion function available, falling back to mock response.")
            return

        # Build prompt
        if places_context and places_context.strip():
            user_prompt = f"""Người dùng hỏi: "{user_message}"

Danh sách quán tìm được:
{places_context}

Hãy giới thiệu các quán này một cách tự nhiên bằng tiếng Việt."""
            system_prompt = SYSTEM_PROMPT
        else:
            # No food keyword found — respond naturally to any message
            user_prompt = f'Người dùng: "{user_message}"'
            system_prompt = SYSTEM_PROMPT_GENERAL

        def _sync_stream() -> list[str]:
            """Run litellm non-streaming completion in a thread, collect full response."""
            try:
                messages: list[dict] = [{"role": "system", "content": system_prompt}]

                # Inject prior conversation turns so the LLM has context
                if history:
                    for msg in history:
                        messages.append(
                            {"role": msg["role"], "content": msg["content"]}
                        )

                messages.append({"role": "user", "content": user_prompt})

                response = completion_fn(
                    model=resolved_model,
                    messages=messages,
                    api_key=self.api_key,
                    max_tokens=500,
                    stream=False,
                )

                tokens: list[str] = []
                try:
                    choices = getattr(response, "choices", []) or []
                    if choices:
                        msg = getattr(choices[0], "message", None)
                        if msg is not None:
                            content = getattr(msg, "content", "") or ""
                            if content:
                                tokens = list(content)
                except (AttributeError, IndexError, TypeError) as e:
                    logger.warning("llm_response_parse_error", error=str(e))

                logger.info(
                    "llm_response_parsed",
                    model=resolved_model,
                    tokens_count=len(tokens),
                )
                return tokens
            except Exception as e:
                logger.error("llm_sync_error", error=str(e), model=resolved_model)
                return []

        try:
            tokens = await asyncio.to_thread(_sync_stream)
            if tokens:
                for token in tokens:
                    yield token
            else:
                logger.warning(
                    "llm_empty_response", model=resolved_model, falling_back="mock"
                )
                async for chunk in self._mock_response(places_context):
                    yield chunk
        except Exception as e:
            logger.error("llm_error", error=str(e))
            async for chunk in self._mock_response(places_context):
                yield chunk

    async def generate_response_simple(
        self,
        user_message: str,
        places_context: str,
        model: str | None = None,
    ) -> str:
        """Non-streaming version - returns full response as string."""
        chunks = []
        async for chunk in self.generate_response(
            user_message, places_context, model=model
        ):
            chunks.append(chunk)
        return "".join(chunks)

    async def _mock_response(self, places_context: str) -> AsyncGenerator[str, None]:
        """Fallback mock response when no API key is available."""
        if places_context and places_context.strip():
            yield "Tôi đã tìm được Top 5 quán ăn cho bạn:\n\n"
            lines = places_context.strip().split("\n")
            for line in lines:
                if line.strip():
                    yield line + "\n"
            yield "\n\nBạn muốn chọn quán nào?"
        else:
            # General / off-topic fallback
            yield "Chào bạn! 👋 Tôi là Foodie Agent, rất vui được trò chuyện cùng bạn. "
            yield "Bạn đang thèm ăn gì hôm nay? Hãy cho tôi biết khu vực và món ưa thích nhé!"


# Global singleton
llm_client = LLMClient()
