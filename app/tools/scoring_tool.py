"""Scoring tool — ranks restaurants by quality and distance."""

from __future__ import annotations

from typing import Any

from app.db.models import Place, ScoredPlace
from app.tools.base import BaseTool


class ScoringTool(BaseTool):
    """Score and rank places using quality (rating) and proximity weights.

    Formula: score = (rating * w_quality) + (1/distance * w_distance)
    """

    name = "calculate_scores"
    description = (
        "Score and rank a list of places by quality and distance. "
        "Returns places sorted by score descending."
    )

    def _run(
        self,
        places: list[dict[str, Any] | Place],
        w_quality: float = 0.6,
        w_distance: float = 0.4,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        scored: list[ScoredPlace] = []

        for place_data in places:
            if isinstance(place_data, dict):
                place = Place(**place_data)
            else:
                place = place_data

            distance_km = max(place.distance_km, 0.1)
            distance_score = 1.0 / distance_km
            score = (place.rating * w_quality) + (distance_score * w_distance)

            scored_place = ScoredPlace(
                **{**place.model_dump(), "score": round(score, 4)},
            )
            scored.append(scored_place)

        # Sort descending by score
        scored.sort(key=lambda p: p.score, reverse=True)

        # Return as dicts for JSON serialisability
        return [s.model_dump() for s in scored]


scoring_tool = ScoringTool()
