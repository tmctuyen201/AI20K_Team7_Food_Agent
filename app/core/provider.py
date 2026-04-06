"""LLM Provider configuration.

Centralizes API key and model configuration per provider.
Reads from .env via Settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from litellm import acompletion

from app.core.config import settings
from app.core.logging import logger


@dataclass
class ModelConfig:
    """Configuration for a single LLM model."""

    provider: str
    model: str
    api_key: str
    api_base: str | None = None


# Provider → LiteLLM model name mapping
_PROVIDER_MODEL_MAP: dict[str, str] = {
    "anthropic": "anthropic/claude-3-5-sonnet-20241022",
    "openai": "openai/gpt-4o-mini-2024-08-06",
}


def _resolve_model(provider: str, model: str) -> str:
    """Resolve effective model name for LiteLLM.

    LiteLLM requires provider prefix when calling via acompletion.
    e.g. "anthropic/claude-3-5-sonnet-20241022", "openai/gpt-4o-mini"
    """
    # Already has provider prefix
    if "/" in model:
        return model

    # Short model names (no prefix) → add provider prefix
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        return f"openai/{model}"
    if model.startswith("claude-"):
        return f"anthropic/{model}"

    # Fallback: look up in map
    mapped = _PROVIDER_MODEL_MAP.get(provider, model)
    return mapped


def get_llm_config() -> ModelConfig:
    """Build ModelConfig from current settings.

    Raises:
        ValueError: If API key is missing for the selected provider.
    """
    provider = settings.llm_provider
    model = _resolve_model(provider, settings.llm_model)

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or settings.anthropic_api_key
    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    if not api_key:
        raise ValueError(
            f"API key missing for provider '{provider}'. "
            f"Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env"
        )

    logger.info(
        "llm_config_resolved",
        provider=provider,
        model=model,
    )

    return ModelConfig(
        provider=provider,
        model=model,
        api_key=api_key,
    )


async def llm_chat(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    stream: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> Any:
    """Call LLM via LiteLLM with full logging.

    Args:
        messages: Chat messages in OpenAI format.
        tools: Optional tool definitions (LiteLLM schema).
        stream: Whether to stream response.
        temperature: Sampling temperature.
        max_tokens: Max tokens in response.

    Returns:
        LiteLLM response object.
    """
    config = get_llm_config()

    logger.info(
        "llm_call_start",
        provider=config.provider,
        model=config.model,
        message_count=len(messages),
        has_tools=tools is not None,
        stream=stream,
    )

    try:
        response = await acompletion(
            model=config.model,
            messages=messages,
            api_key=config.api_key,
            tools=tools,
            stream=False,  # Disable streaming for tool-calling mode
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(
            "llm_call_success",
            provider=config.provider,
            model=config.model,
        )
        return response

    except Exception as e:
        logger.error(
            "llm_call_failed",
            provider=config.provider,
            model=config.model,
            error=str(e),
        )
        raise


def llm_chat_sync(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    stream: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> Any:
    """Synchronous LLM call via LiteLLM.

    Use in non-async contexts (e.g. tool callbacks).
    """
    from litellm import completion

    config = get_llm_config()

    logger.info(
        "llm_call_sync_start",
        provider=config.provider,
        model=config.model,
        message_count=len(messages),
        has_tools=tools is not None,
    )

    try:
        response = completion(
            model=config.model,
            messages=messages,
            api_key=config.api_key,
            tools=tools,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info(
            "llm_call_sync_success",
            provider=config.provider,
            model=config.model,
        )
        return response

    except Exception as e:
        logger.error(
            "llm_call_sync_failed",
            provider=config.provider,
            model=config.model,
            error=str(e),
        )
        raise
