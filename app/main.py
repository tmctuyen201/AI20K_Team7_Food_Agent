"""Main entry point — Phase 1 CLI runner.

Run interactively from terminal:
    python -m app.main
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

# Ensure logs dir exists
(Path(__file__).parent.parent / "logs").mkdir(exist_ok=True)

from app.agent.react_agent import ReActAgent
from app.agent.state import AgentState
from app.core.logging import get_logger, SessionLogHandler
from app.tools.definitions import get_tool_definitions
from app.tools.mock_data import MOCK_USERS

logger = get_logger("foodie.main")


def print_banner() -> None:
    banner = """
╔═══════════════════════════════════════════╗
║        🍜 Foodie Agent — Phase 1          ║
║   ReAct chatbot tìm quán ăn               ║
╚═══════════════════════════════════════════╝
"""
    print(banner)


def print_user_options() -> None:
    print("\n[Users mock — chọn user_id để bắt đầu]")
    for u in MOCK_USERS:
        print(f"  {u['user_id']} — {u['name']} ({u['city']})")
    print()


async def run_chat(user_id: str, session_id: str) -> None:
    """Run a single chat session."""
    print(f"\n{'='*50}")
    print(f"Session: {session_id}")
    print(f"User: {user_id} (mock)")
    print(f"{'='*50}")
    print("\n💬 Bạn (gõ 'exit' để thoát, 'reset' để xóa cuộc trò chuyện):\n")

    # Attach session file logging
    session_handler = SessionLogHandler(session_id)
    session_handler.attach()
    logger.info("session_started", user_id=user_id, session_id=session_id)

    try:
        agent = ReActAgent(tools=get_tool_definitions())
        state: AgentState = {
            "user_id": user_id,
            "session_id": session_id,
            "user_message": "",
            "rejection_count": 0,
            "is_done": False,
            "radius": 2000,
            "open_now": True,
            "sort_by": "prominence",
            "tool_calls": [],
            "shown_place_ids": [],
        }

        while True:
            user_input = input("👤 Bạn: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("\n👋 Tạm biệt!")
                break
            if user_input.lower() == "reset":
                state["tool_calls"] = []
                state["rejection_count"] = 0
                state["is_done"] = False
                state["final_response"] = None
                print("\n🔄 Đã reset cuộc trò chuyện.\n")
                continue

            logger.info("user_message", user_id=user_id, message=user_input[:100])
            state["user_message"] = user_input

            # Run agent
            print("\n🤖 Foodie Agent: đang suy nghĩ...")
            state = await agent.run(state)

            # Print response
            response = state.get("final_response", "")
            if response:
                print(f"\n🤖 Foodie Agent:\n{response}\n")

            # Log tool calls summary
            tool_calls = state.get("tool_calls", [])
            if tool_calls:
                logger.info(
                    "session_tool_summary",
                    session_id=session_id,
                    tool_count=len(tool_calls),
                    tools=[tc["tool"] for tc in tool_calls],
                )
            else:
                logger.warning("session_no_tools", session_id=session_id)

    finally:
        session_handler.detach()
        logger.info("session_ended", user_id=user_id, session_id=session_id)


async def main() -> None:
    """Phase 1 main: interactive CLI chat."""
    print_banner()
    print_user_options()

    user_id = input("Chọn user_id (mặc định u01): ").strip() or "u01"
    session_id = f"sess_{uuid.uuid4().hex[:8]}"

    await run_chat(user_id, session_id)


if __name__ == "__main__":
    asyncio.run(main())