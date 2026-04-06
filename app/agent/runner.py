"""Agent runner — wraps LangGraph agent with LLM response generation."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

from app.agent.graph import create_agent_graph
from app.agent.state import AgentState
from app.db.models import ScoredPlace
from app.core.logging import get_agent_logger
from app.services.llm import llm_client

agent_logger = get_agent_logger()


class AgentRunner:
    """Wrapper around LangGraph agent with LLM-powered responses."""

    def __init__(self, user_id: str, session_id: str) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.graph = create_agent_graph()
        self._final_places: list[ScoredPlace] = []
        self._rejection_count: int = 0

    def _build_places_context(self, places: list[ScoredPlace]) -> str:
        """Build context string from places for LLM."""
        if not places:
            return ""

        lines = []
        for i, place in enumerate(places[:5], 1):
            lines.append(f"{i}. {place.name}")
            lines.append(f"   - Rating: {place.rating}/5 sao")
            lines.append(f"   - Khoảng cách: {place.distance_km:.1f} km")
            if place.cuisine_type:
                lines.append(f"   - Loại món: {place.cuisine_type}")
            if place.address:
                lines.append(f"   - Địa chỉ: {place.address}")
            if place.open_now:
                lines.append("   - Đang mở cửa")
            lines.append("")

        return "\n".join(lines)

    def _run_graph_sync(self, user_message: str) -> tuple[list[ScoredPlace], str | None]:
        """Run the graph synchronously.

        Returns:
            Tuple of (scored_places, intent).
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

        result = self.graph.invoke(initial_state)
        scored_places = result.get("scored_places") or []

        # Log node messages
        for msg in result.get("messages") or []:
            agent_logger.debug("node_log", node_message=msg)

        return scored_places

    async def run_async(self, user_message: str) -> AsyncGenerator[str, None]:
        """Run agent and generate LLM response (async version).

        Yields:
            Token strings from LLM to send over WebSocket.
        """
        agent_logger.info(
            "runner_run_start",
            user_id=self.user_id,
            session_id=self.session_id,
            message_preview=user_message[:100],
        )

        # Run graph in thread pool (it's synchronous)
        loop = asyncio.get_running_loop()
        scored_places = await loop.run_in_executor(
            None, self._run_graph_sync, user_message
        )

        self._final_places = scored_places

        # Build places context for LLM (empty = LLM responds naturally as food agent)
        places_context = self._build_places_context(scored_places)

        # Generate LLM response (streaming)
        async for chunk in llm_client.generate_response(user_message, places_context):
            yield chunk

        agent_logger.info(
            "runner_run_complete",
            user_id=self.user_id,
            session_id=self.session_id,
            places_count=len(scored_places),
        )

    def get_final_places(self) -> list[ScoredPlace]:
        """Return the scored places from the last agent run."""
        return self._final_places

    def handle_rejection(self) -> Optional[str]:
        """Handle when user rejects all suggestions."""
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
