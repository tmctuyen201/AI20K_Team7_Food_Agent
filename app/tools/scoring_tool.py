"""Scoring tool — ranks restaurants by quality and distance."""

from __future__ import annotations

from typing import Any

from app.db.models import Place, ScoredPlace
from app.tools.base import BaseTool


class ScoringTool(BaseTool):
    """Score and rank places using quality (rating) and proximity weights.

    Formula: score = (rating * w_quality) + (w_distance / max(dist_km, 0.1))
    """

    name = "calculate_scores"
    description = (
        "Tính điểm và xếp hạng quán ăn dựa trên rating và khoảng cách. "
        "Trả về danh sách quán đã sắp xếp theo điểm giảm dần."
    )

    @staticmethod
    def _parse_km(val: Any) -> float:
        """Parse distance value (km or m) to float km."""
        try:
            s = str(val).lower().strip()
            if "km" in s:
                return float(s.replace("km", "").strip())
            if "m" in s:
                return float(s.replace("m", "").strip()) / 1000
            return float(s)
        except Exception:
            return 1.0

    def _run(
        self,
        places: list[dict[str, Any] | Any],
        w_quality: float = 0.6,
        w_distance: float = 0.4,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if not places:
            return []

        scored: list[ScoredPlace] = []
        for place_data in places:
            if isinstance(place_data, dict):
                # Normalise: handle "distance" string or "distance_km" float
                raw_dist = place_data.get("distance") or place_data.get("distance_km") or 1.0
                dist_km = self._parse_km(raw_dist)
                dist_km = max(dist_km, 0.1)
                dist_score = w_distance / dist_km
                rating = float(place_data.get("rating") or 0.0)
                score = (rating * w_quality) + dist_score

                place_dict = {
                    **{k: v for k, v in place_data.items() if k not in ("distance", "total_score")},
                    "distance_km": round(dist_km, 2),
                    "score": round(score, 4),
                }
                scored.append(ScoredPlace(**place_dict))
            else:
                place = Place(name=str(place_data))

        # Sort descending by score
        scored.sort(key=lambda p: p.score, reverse=True)
        return [s.model_dump() for s in scored]


scoring_tool = ScoringTool()
