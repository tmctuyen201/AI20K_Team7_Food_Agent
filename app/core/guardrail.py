"""Guardrail layer — runs after each ReAct iteration."""

from __future__ import annotations

from app.core.logging import get_logger
from app.agent.state import AgentState

logger = get_logger("foodie.guardrail")


class GuardrailResult:
    """Result of a guardrail check."""

    def __init__(
        self,
        triggered: bool = False,
        name: str = "",
        message: str = "",
    ):
        self.triggered = triggered
        self.name = name
        self.message = message


def check_guardrails(state: AgentState) -> GuardrailResult:
    """Run all guardrails on the current agent state.

    Returns GuardrailResult indicating if a guardrail was triggered.
    """
    checkers = [
        _check_zero_results,
        _check_max_retries,
        _check_midnight_filter,
    ]

    for checker in checkers:
        result = checker(state)
        if result.triggered:
            return result

    return GuardrailResult()


def _check_zero_results(state: AgentState) -> GuardrailResult:
    """Zero Result guardrail: API returned no results."""
    places = state.get("places_raw", [])
    if not places and state.get("keyword"):
        logger.warning(
            "guardrail_zero_results",
            keyword=state.get("keyword"),
            user_id=state.get("user_id"),
        )
        return GuardrailResult(
            triggered=True,
            name="Zero Result",
            message=(
                f"Không tìm thấy quán nào với từ khóa '{state.get('keyword')}' "
                "trong khu vực này. Bạn muốn thử từ khóa khác hoặc tăng bán kính tìm kiếm không?"
            ),
        )
    return GuardrailResult()


def _check_max_retries(state: AgentState) -> GuardrailResult:
    """Max Retries guardrail: user rejected ≥3 times."""
    rejection_count = state.get("rejection_count", 0)
    if rejection_count >= 3:
        logger.warning(
            "guardrail_max_retries",
            rejection_count=rejection_count,
            user_id=state.get("user_id"),
        )
        return GuardrailResult(
            triggered=True,
            name="Max Retries",
            message=(
                "Bạn đã không hài lòng với nhiều gợi ý. "
                "Bạn có thể cho tôi biết thêm về ngân sách, "
                "phong cách quán, hoặc khu vực bạn muốn không?"
            ),
        )
    return GuardrailResult()


def _check_midnight_filter(state: AgentState) -> GuardrailResult:
    """Midnight Filter: warn if few places are open (22:00 - 05:00)."""
    from datetime import datetime
    hour = datetime.now().hour
    if not (22 <= hour or hour < 5):
        return GuardrailResult()

    places = state.get("places_raw", [])
    open_places = [
        p for p in places
        if p.get("opening_hours", {}).get("open_now") is True
    ]

    if places and len(open_places) < 5:
        logger.warning(
            "guardrail_midnight_filter",
            open_count=len(open_places),
            total_count=len(places),
        )
        return GuardrailResult(
            triggered=True,
            name="Midnight Filter",
            message=(
                f"Hiện tại chỉ có {len(open_places)} quán đang mở cửa. "
                "Bạn có muốn xem danh sách này hay đợi đến sáng?"
            ),
        )
    return GuardrailResult()