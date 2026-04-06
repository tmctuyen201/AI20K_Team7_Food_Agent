"""Base class for all agent tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base that all tools must inherit from."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def _run(self, **kwargs: Any) -> Any:
        """Synchronous tool implementation (required)."""
        raise NotImplementedError

    async def _arun(self, **kwargs: Any) -> Any:
        """Async wrapper — default calls _run synchronously."""
        return self._run(**kwargs)
