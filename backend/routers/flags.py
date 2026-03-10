"""
Performance flags browser router.

Browse players by calculated performance flags (Breakout, Trending Up, etc.).
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from models.schemas import (
    PlayerBase,
    PlayerProjection,
    RecentPerformance,
)
from services.calibration import get_calibration_summary, resolve_predictions
from services.enhancement import get_enhancement_engine
from services.player_enrichment import resolve_projection
from services.sleeper import get_sleeper_client

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_FLAGS = [
    "BREAKOUT_CANDIDATE",
    "TRENDING_UP",
    "UNDERPERFORMING",
    "DECLINING_ROLE",
    "HIGH_CEILING",
    "BOOM_BUST",
    "CONSISTENT",
]

POOL_SIZE_MIN = 500
POOL_SIZE_MAX = 2000
POOL_SIZE_MULTIPLIER = 20


@router.get("/calibration")
async def get_calibration():
    """
    Get prediction calibration stats — how accurate are Pulse recommendations?

    Optionally triggers a backfill of unresolved predictions against actual stats.
    """
    # Try to resolve any pending predictions first
    try:
        await resolve_predictions()
    except Exception as e:
        logger.warning(f"Calibration backfill failed: {e}")

    summary = get_calibration_summary()
    return summary


@router.get("/by-flag/{flag}")
async def get_players_by_flag(
    flag: str,
    position: Optional[str] = Query(
        None, description="Filter by position (QB, RB, WR, TE, K, DEF)"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
):
    """
    Get players that have a specific performance flag.
    Use this to find breakout candidates, trending players, etc.
    """
    flag_upper = flag.upper()
    if flag_upper not in VALID_FLAGS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid flag. Valid flags: {', '.join(VALID_FLAGS)}",
        )

    client = get_sleeper_client()
    engine = get_enhancement_engine()
    settings = get_settings()
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    pool_size = min(POOL_SIZE_MAX, max(POOL_SIZE_MIN, limit * POOL_SIZE_MULTIPLIER))
    players = await client.get_active_players_by_position(
        position=position, limit=pool_size
    )

    logger.info(f"Checking {len(players)} players for flag {flag_upper}")

    matching_players = []

    for player_data in players:
        try:
            on_bye = player_data.get("bye_week") == current_week

            perf_data = await client.get_recent_performance(
                player_data["sleeper_id"],
                current_season,
                current_week,
                lookback=3,
            )

            if not perf_data or perf_data.get("weeks_analyzed", 0) == 0:
                continue

            perf = RecentPerformance(**perf_data)

            # Resolve projection using the shared fallback chain
            projection_value, _ = await resolve_projection(
                client,
                player_data["sleeper_id"],
                current_season,
                current_week,
                perf,
                on_bye,
            )

            flags = []
            if not on_bye and projection_value > 0:
                flags = engine.calculate_flags(projection_value, perf)

            if flag_upper in flags:
                player = PlayerBase(**player_data)
                projection = PlayerProjection(
                    sleeper_projection=projection_value,
                    adjusted_projection=engine.calculate_adjusted_projection(
                        projection_value, perf, flags
                    ),
                )

                matching_players.append(
                    {
                        "player": player.model_dump(),
                        "projection": projection.model_dump(),
                        "recent_performance": perf.model_dump(),
                        "performance_flags": flags,
                        "context_message": f"L{perf.weeks_analyzed}W avg: {perf.avg_points} pts",
                        "on_bye": on_bye,
                    }
                )

                if len(matching_players) >= limit:
                    break

        except Exception as e:
            logger.warning(
                f"Error processing player {player_data.get('name')}: {e}"
            )
            continue

    matching_players.sort(
        key=lambda p: p["recent_performance"]["avg_points"]
        if p["recent_performance"]
        else 0,
        reverse=True,
    )

    logger.info(f"Found {len(matching_players)} players with flag {flag_upper}")

    return {
        "flag": flag_upper,
        "count": len(matching_players),
        "players": matching_players,
    }


@router.get("/flags/available")
async def get_available_flags():
    """Get list of available flags for the browser."""
    return {
        "flags": [
            {
                "id": "BREAKOUT_CANDIDATE",
                "label": "\U0001f680 Breakout",
                "description": "L3W avg > 150% of projection",
            },
            {
                "id": "TRENDING_UP",
                "label": "\U0001f4c8 Trending Up",
                "description": "L3W avg > 120% of projection",
            },
            {
                "id": "UNDERPERFORMING",
                "label": "\U0001f4c9 Underperforming",
                "description": "L3W avg < 80% of projection",
            },
            {
                "id": "DECLINING_ROLE",
                "label": "\u26a0\ufe0f Declining",
                "description": "L3W avg < 70% of projection",
            },
            {
                "id": "HIGH_CEILING",
                "label": "\U0001f3af High Ceiling",
                "description": "Best week > 200% of projection",
            },
            {
                "id": "BOOM_BUST",
                "label": "\U0001f3b0 Boom/Bust",
                "description": "High variance player",
            },
            {
                "id": "CONSISTENT",
                "label": "\u2705 Consistent",
                "description": "Low variance, reliable",
            },
        ]
    }
