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


def check_irrelevant_input(state: AgentState) -> GuardrailResult:
    """Irrelevant Input guardrail: input does not relate to food/restaurants."""
    keyword = state.get("keyword", "").strip().lower()
    
    if not keyword:
        return GuardrailResult()
    
    # Food, location, and time-related keywords to match
    food_keywords = [
        "quán", "nhà hàng", "cơm", "phở", "bánh", "nước", "cà phê", "trà",
        "ăn", "uống", "kem", "pizza", "mì", "bún", "cơm tấm", "lẩu",
        "noodles", "restaurant", "food", "cafe", "coffee", "drink",
        "pizza", "burger", "steak", "sushi", "ramen", "shop",
    ]
    location_keywords = [
        "quận", "huyện", "thành phố", "tp", "phường", "đường", "street", "district", "ward", "city", "address", "gần", "bên cạnh", "khu vực", "location", "ở đâu", "near", "close to", "vị trí"
    ]
    greeting_keywords = [
        "xin chào","xin chao", "chào", "hello", "hi", "hey", "alo", "bạn là ai", "bạn làm gì", "help", "trợ giúp", "hướng dẫn", "bạn khỏe không", "good morning", "good afternoon", "good evening", "good night", "greetings", "mình muốn hỏi", "cho hỏi", "tôi muốn hỏi"
    ]

    # Nếu là câu chào/hỏi thì không kích hoạt guardrail
    if any(greet in keyword for greet in greeting_keywords):
        return GuardrailResult()

    # Check if keyword contains any relevant term
    if not (
        any(food_term in keyword for food_term in food_keywords)
        or any(loc_term in keyword for loc_term in location_keywords)
    ):
        logger.warning(
            "guardrail_irrelevant_input",
            keyword=keyword,
            user_id=state.get("user_id"),
        )
        return GuardrailResult(
            triggered=True,
            name="Irrelevant Input",
            message=(
                f"Câu hỏi của bạn không liên quan đến quán ăn, địa điểm hoặc thời gian. "
                "Bạn muốn tìm kiếm loại quán ăn, khu vực hoặc thời gian cụ thể nào không? "
                "(Ví dụ: phở quận 1, pizza tối nay, cà phê gần đây, ...)"
            ),
        )
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