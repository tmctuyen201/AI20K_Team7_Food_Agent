"""Agent runner — wraps the LangGraph agent with streaming and state access."""

from __future__ import annotations

import asyncio
import re
from typing import AsyncGenerator, Optional

from app.agent.graph import create_agent_graph
from app.agent.state import AgentState
from app.db.models import ScoredPlace
from app.core.logging import get_agent_logger

agent_logger = get_agent_logger()


class AgentRunner:
    """Wrapper around the LangGraph StateGraph that provides:

    - ``run()`` → async generator yielding response tokens
    - ``get_final_places()`` → returns the scored places after a run
    - ``handle_rejection()`` → expands search radius on user rejection
    """

    def __init__(self, user_id: str, session_id: str) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.graph = create_agent_graph()
        self._final_places: list[ScoredPlace] = []
        self._rejection_count: int = 0

    def run(self, user_message: str) -> AsyncGenerator[str, None]:
        """Run the LangGraph agent for one user message, yielding tokens.

        Args:
            user_message: The raw text from the user.

        Yields:
            Token strings (sentence-length chunks) to send over WebSocket.
        """
        initial_state: AgentState = {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "user_message": user_message,
            "intent": None,
            "location": None,
            "keyword": None,
            "places": [],
            "scored_places": [],
            "shown_place_ids": [],
            "rejection_count": self._rejection_count,
            "next_page_token": None,
            "last_radius": 2000,
            "messages": [],
            "is_complete": False,
        }

        agent_logger.info(
            "runner_run_start",
            user_id=self.user_id,
            session_id=self.session_id,
            message_preview=user_message[:100],
        )

        # Run the compiled graph synchronously (blocking)
        # The graph itself calls async services via run_until_complete in tools
        result = self.graph.invoke(initial_state)

        # Parse scored places from the result
        scored_places = result.get("scored_places") or []
        self._final_places = scored_places

        # Append any log messages from node executions
        node_messages = result.get("messages") or []
        for msg in node_messages:
            agent_logger.debug("node_log", node_message=msg)

        if not scored_places:
            yield "Xin lỗi, tôi không tìm thấy quán phù hợp. Bạn có thể cho tôi biết thêm địa chỉ không?"
            return

        yield "Tôi đã tìm được Top 5 quán ăn cho bạn:\n\n"

        for i, place in enumerate(scored_places, 1):
            yield f"{i}. **{place.name}**\n"
            yield f"   ⭐ Rating: {place.rating}/5\n"
            yield f"   📍 Khoảng cách: {place.distance_km:.1f} km\n"
            if place.cuisine_type:
                yield f"   🍜 Loại: {place.cuisine_type}\n"
            yield "\n"

        yield "Bạn muốn chọn quán nào?"

        agent_logger.info(
            "runner_run_complete",
            user_id=self.user_id,
            session_id=self.session_id,
            places_count=len(scored_places),
        )

    async def run_async(self, user_message: str) -> AsyncGenerator[str, None]:
        """Async wrapper — delegates to the synchronous run().

        Phase 1 streaming: yields sentence-length chunks.
        Replace with real streaming in a later iteration.
        """
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: list(self.run(user_message)))

        for chunk in response:
            yield chunk

    def get_final_places(self) -> list[ScoredPlace]:
        """Return the scored places from the last agent run."""
        return self._final_places

    def handle_rejection(self) -> Optional[str]:
        """Handle when user rejects all suggestions.

        Increments rejection count and expands the search radius.
        Returns None if max rejections (3) have been reached.
        """
        self._rejection_count += 1

        if self._rejection_count >= 3:
            agent_logger.warning(
                "rejection_max_reached",
                user_id=self.user_id,
                session_id=self.session_id,
                rejection_count=self._rejection_count,
            )
            return (
                "Bạn đã từ chối nhiều gợi ý liên tiếp. "
                "Bạn có thể cho tôi biết thêm về ngân sách, "
                "loại quán mong muốn hoặc khu vực cụ thể không?"
            )

        agent_logger.info(
            "rejection_handled",
            user_id=self.user_id,
            session_id=self.session_id,
            rejection_count=self._rejection_count,
        )
        return None

    def reset_rejection_count(self) -> None:
        """Reset the rejection counter after a successful selection."""
        self._rejection_count = 0
