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
        _check_ambiguous_location,
        _check_zero_results,
        _check_max_retries,
        _check_midnight_filter,
        _check_mock_location,
    ]

    for checker in checkers:
        result = checker(state)
        if result.triggered:
            return result

    return GuardrailResult()


# ── Individual guardrail checkers ──────────────────────────────────────────────

def _check_ambiguous_location(state: AgentState) -> GuardrailResult:
    """Ambiguous Location guardrail: confidence too low or multiple matches possible."""
    if not state.get("ambiguous_location"):
        return GuardrailResult()

    logger.warning(
        "guardrail_ambiguous_location",
        confidence=state.get("location_confidence", 0),
        user_id=state.get("user_id"),
    )
    return GuardrailResult(
        triggered=True,
        name="Ambiguous Location",
        message=(
            "Mình chưa xác định chính xác khu vực của bạn. "
            "Bạn có thể cho biết rõ hơn địa chỉ hoặc thành phố/quận bạn đang ở không?"
        ),
    )


def _check_mock_location(state: AgentState) -> GuardrailResult:
    """Mock Location guardrail: used mock data when no GPS/headers available."""
    location = state.get("location")
    # location can be a LatLng pydantic model, a dict, or None
    if hasattr(location, "source"):
        source = location.source
    elif isinstance(location, dict):
        source = location.get("source", "")
    else:
        source = ""
    source = source or state.get("location_source", "")

    if source != "mock_data":
        return GuardrailResult()

    # Only trigger if the user hasn't confirmed the address already
    if state.get("address_confirmed"):
        return GuardrailResult()

    logger.warning(
        "guardrail_mock_location",
        user_id=state.get("user_id"),
        source=source,
    )
    return GuardrailResult(
        triggered=True,
        name="Mock Location",
        message=(
            "Mình chưa xác định được vị trí chính xác của bạn. "
            "Bạn có thể cho biết địa chỉ hoặc khu vực đang ở không?"
        ),
    )


def _check_zero_results(state: AgentState) -> GuardrailResult:
    """Zero Result guardrail: API returned no results."""
    # v2 pipeline stores places as "places" (list) + "scored_places" (top-5)
    # async/stream pipeline uses "places_raw" (dict list) + "places_scored"
    # Guard checks all keys so either pipeline path triggers correctly
    places_raw = state.get("places_raw", [])
    places_v2 = state.get("places", [])
    scored = state.get("scored_places", [])
    places_scored = state.get("places_scored", [])

    places: list = places_raw or places_v2 or scored or places_scored

    # DEBUG
    logger.debug(
        "zero_check",
        places_raw_len=len(places_raw),
        places_v2_len=len(places_v2),
        scored_len=len(scored),
        places_scored_len=len(places_scored),
        keyword=state.get("keyword", ""),
        will_trigger=not places and bool(state.get("keyword")),
    )

    keyword = state.get("keyword", "")

    # Only trigger if search has actually run — guardrail fires during the
    # location-only check before search_places() is even called
    if state.get("search_done") is not True:
        return GuardrailResult()

    if not places and keyword:
        logger.warning(
            "guardrail_zero_results",
            keyword=keyword,
            user_id=state.get("user_id"),
        )
        return GuardrailResult(
            triggered=True,
            name="Zero Result",
            message=(
                f"Không tìm thấy quán nào với từ khóa '{keyword}' "
                "trong bán kính 2km quanh đây.\n\n"
                "Bạn có muốn mình mở rộng tìm kiếm ra 10km hoặc thử từ khóa khác "
                "(như cơm, bún, hải sản) không?"
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
                "Dường như mình chưa tìm đúng gu của bạn. "
                "Để chính xác hơn, bạn thích không gian như thế nào "
                "(vỉa hè / sang trọng / bình dân) hoặc ngân sách khoảng bao nhiêu?"
            ),
        )
    return GuardrailResult()


def _check_midnight_filter(state: AgentState) -> GuardrailResult:
    """Midnight Filter: warn if few places are open (22:00 - 05:00)."""
    from datetime import datetime

    hour = datetime.now().hour
    # Late night / early morning: 22h - 5h
    if not (hour >= 22 or hour < 5):
        return GuardrailResult()

    # Guard checks all key variants so either pipeline path triggers correctly
    places_raw = state.get("places_raw", [])
    places_v2 = state.get("places", [])
    scored = state.get("scored_places", [])
    places_scored = state.get("places_scored", [])
    places: list = places_raw or places_v2 or scored or places_scored

    if not places:
        return GuardrailResult()

    # Only trigger if search has actually run
    if state.get("search_done") is not True:
        return GuardrailResult()

    # open_now lives at the top-level of Place dicts and ScoredPlace objects
    def _is_open(p) -> bool:
        return bool(
            getattr(p, "open_now", None) is True
            or (isinstance(p, dict) and p.get("open_now") is True)
            or (isinstance(p, dict) and p.get("opening_hours", {}).get("open_now") is True)
        )

    open_places = [p for p in places if _is_open(p)]

    total = len(places)
    open_count = len(open_places)

    if open_count >= 5:
        return GuardrailResult()

    logger.warning(
        "guardrail_midnight_filter",
        open_count=open_count,
        total_count=total,
        hour=hour,
    )

    # Only 1-2 places open — suggest alternatives
    if open_count == 0:
        message = (
            f"Hiện tại đã muộn ({hour}h), không có quán nào đang mở cửa. "
            "Bạn có muốn mình tìm các quán ăn đêm/vỉa hè gần đây không?"
        )
    else:
        open_names = ", ".join([p.get("name", "") for p in open_places[:2]])
        message = (
            f"Hiện tại đã muộn ({hour}h), chỉ có {open_count} quán đang mở: {open_names}. "
            "Bạn có muốn mình tìm thêm các quán ăn đêm/vỉa hè khác cho bạn không?"
        )

    return GuardrailResult(
        triggered=True,
        name="Midnight Filter",
        message=message,
    )