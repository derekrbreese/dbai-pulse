"""
Calibration service — resolves prediction outcomes against actual stats.

Fetches actual fantasy points from Sleeper for unresolved predictions,
compares against projected points, and marks outcomes.
"""

import logging
from typing import Optional

from services.sleeper import get_sleeper_client
from services.storage import get_storage

logger = logging.getLogger(__name__)

# Outcome thresholds
ACTUAL_VS_PROJECTED_THRESHOLD = 0.80  # 80% of projected


def _determine_outcome(
    recommendation: str,
    projected_points: Optional[float],
    actual_points: float,
) -> str:
    """
    Determine if a prediction was correct.

    Rules:
    - START + actual >= 80% of projected → CORRECT
    - START + actual <  80% of projected → INCORRECT
    - SIT   + actual <  80% of projected → CORRECT
    - SIT   + actual >= 80% of projected → INCORRECT
    - FLEX  → always NEUTRAL
    """
    rec = recommendation.upper()
    if rec == "FLEX":
        return "NEUTRAL"

    if projected_points is None or projected_points <= 0:
        return "NEUTRAL"

    hit_threshold = actual_points >= (projected_points * ACTUAL_VS_PROJECTED_THRESHOLD)

    if rec == "START":
        return "CORRECT" if hit_threshold else "INCORRECT"
    if rec == "SIT":
        return "CORRECT" if not hit_threshold else "INCORRECT"

    return "NEUTRAL"


async def resolve_predictions(season: Optional[int] = None, week: Optional[int] = None) -> dict:
    """
    Backfill actual stats for unresolved predictions.

    Returns summary of how many were resolved.
    """
    storage = get_storage()
    client = get_sleeper_client()

    unresolved = storage.get_unresolved_predictions(season=season, week=week)
    if not unresolved:
        return {"resolved": 0, "skipped": 0, "message": "No unresolved predictions"}

    resolved_count = 0
    skipped_count = 0

    for pred in unresolved:
        pred_id = pred["id"]
        sleeper_id = pred["sleeper_id"]
        pred_season = pred["season"]
        pred_week = pred["week"]

        try:
            stats = await client.get_player_stats(sleeper_id, pred_season, pred_week)
            if not stats:
                skipped_count += 1
                continue

            actual_pts = None
            for key in ("pts_ppr", "pts_half_ppr", "pts_std", "pts"):
                val = stats.get(key)
                if val is not None:
                    actual_pts = float(val)
                    break

            if actual_pts is None:
                skipped_count += 1
                continue

            outcome = _determine_outcome(
                pred["recommendation"],
                pred.get("projected_points"),
                actual_pts,
            )

            storage.resolve_prediction(pred_id, actual_pts, outcome)
            resolved_count += 1

        except Exception as e:
            logger.warning(f"Failed to resolve prediction {pred_id}: {e}")
            skipped_count += 1

    return {
        "resolved": resolved_count,
        "skipped": skipped_count,
        "total_checked": len(unresolved),
    }


def get_calibration_summary() -> dict:
    """
    Build calibration stats from resolved predictions.

    Returns accuracy breakdown by conviction level and recommendation type.
    """
    storage = get_storage()
    rows = storage.get_calibration_stats()

    if not rows:
        return {
            "total_resolved": 0,
            "overall_accuracy": None,
            "by_conviction": {},
            "by_recommendation": {},
            "predictions": [],
        }

    total = len(rows)
    correct = sum(1 for r in rows if r["outcome"] == "CORRECT")
    neutral = sum(1 for r in rows if r["outcome"] == "NEUTRAL")
    scoreable = total - neutral

    # By conviction
    by_conviction = {}
    for row in rows:
        conv = row["conviction"]
        if conv not in by_conviction:
            by_conviction[conv] = {"total": 0, "correct": 0, "incorrect": 0, "neutral": 0}
        by_conviction[conv]["total"] += 1
        by_conviction[conv][row["outcome"].lower()] = by_conviction[conv].get(row["outcome"].lower(), 0) + 1

    for conv, stats in by_conviction.items():
        denom = stats["total"] - stats["neutral"]
        stats["accuracy"] = round(stats["correct"] / denom, 3) if denom > 0 else None

    # By recommendation
    by_rec = {}
    for row in rows:
        rec = row["recommendation"]
        if rec not in by_rec:
            by_rec[rec] = {"total": 0, "correct": 0, "incorrect": 0, "neutral": 0}
        by_rec[rec]["total"] += 1
        by_rec[rec][row["outcome"].lower()] = by_rec[rec].get(row["outcome"].lower(), 0) + 1

    for rec, stats in by_rec.items():
        denom = stats["total"] - stats["neutral"]
        stats["accuracy"] = round(stats["correct"] / denom, 3) if denom > 0 else None

    return {
        "total_resolved": total,
        "overall_accuracy": round(correct / scoreable, 3) if scoreable > 0 else None,
        "by_conviction": by_conviction,
        "by_recommendation": by_rec,
        "predictions": rows,
    }
