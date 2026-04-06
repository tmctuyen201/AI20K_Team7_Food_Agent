"""Scoring tool — ranks restaurants by quality and distance."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("foodie.scoring")


def score_places(
    places: list[dict[str, Any]],
    w_quality: float = 0.6,
    w_distance: float = 0.4,
    default_distance_km: float = 5.0,
) -> list[dict[str, Any]]:
    """Score and rank places using quality and distance weights.

    Formula: score = (rating * w_quality) + (1/distance * w_distance)

    Args:
        places: Raw place dicts from Google Places API.
        w_quality: Weight for rating (0.0 - 1.0).
        w_distance: Weight for proximity (0.0 - 1.0).
        default_distance_km: Fallback distance when not available.

    Returns:
        Places sorted by score descending, each with a "score" key added.
    """
    scored = []

    for place in places:
        rating = place.get("rating") or 0.0
        distance_raw = place.get("geometry", {}).get("distance_meters")

        if distance_raw:
            distance_km = distance_raw / 1000.0
        else:
            distance_km = default_distance_km

        score = (rating * w_quality) + (1.0 / max(distance_km, 0.1) * w_distance)

        scored_place = {
            **place,
            "score": round(score, 4),
            "distance_km": round(distance_km, 2),
        }
        scored.append(scored_place)

    scored.sort(key=lambda p: p["score"], reverse=True)
    top_5 = scored[:5]

    logger.info(
        "scoring_completed",
        input_count=len(places),
        output_count=len(top_5),
        w_quality=w_quality,
        w_distance=w_distance,
    )

    return top_5