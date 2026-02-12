"""
Player Enrichment Service for dbAI Pulse.

Consolidates the player data fetching, projection fallback chain,
flag calculation, and EnhancedPlayer construction that was previously
duplicated across multiple router endpoints.
"""

import logging
from typing import List, Optional, Tuple

from config import get_settings
from models.schemas import (
    DraftValue,
    EnhancedPlayer,
    PlayerBase,
    PlayerProjection,
    RecentPerformance,
)
from services.adp import get_adp_service
from services.enhancement import calculate_draft_value, get_enhancement_engine
from services.sleeper import get_sleeper_client

logger = logging.getLogger(__name__)


async def resolve_projection(
    client,
    sleeper_id: str,
    season: int,
    week: int,
    recent_performance: Optional[RecentPerformance],
    on_bye: bool,
) -> Tuple[float, str]:
    """
    Resolve the best available projection using the fallback chain:
    1. Sleeper projection for current week
    2. Recent projection average (L3W)
    3. Prior-week average (excludes most recent week)
    4. L3W average points

    Returns (projection_value, projection_source).
    """
    projection_value = 0.0
    projection_source = "sleeper"

    if not on_bye:
        projection_value = await client.get_player_projection(
            sleeper_id, season, week
        )

    previous_avg = 0.0
    if recent_performance and len(recent_performance.weekly_points) > 1:
        previous_avg = sum(recent_performance.weekly_points[1:]) / (
            len(recent_performance.weekly_points) - 1
        )

    if projection_value == 0 and recent_performance and not on_bye:
        projection_value = await client.get_recent_projection_avg(
            sleeper_id, season, week, lookback=3
        )
        if projection_value > 0:
            projection_source = "recent_projection"

    if projection_value == 0 and previous_avg > 0:
        projection_value = round(previous_avg, 1)
        projection_source = "recent_baseline"

    if projection_value == 0 and recent_performance:
        projection_value = recent_performance.avg_points
        projection_source = "recent_avg"

    return projection_value, projection_source


def build_context_message(
    on_bye: bool,
    bye_week: Optional[int],
    projection_source: str,
    flags: List[str],
    projection_value: float,
    adjusted_value: Optional[float],
    recent_performance: Optional[RecentPerformance],
) -> str:
    """Build the human-readable context message for a player card."""
    if on_bye:
        return f"Player is on bye (Week {bye_week})"

    if projection_source == "recent_avg" and recent_performance:
        return (
            f"Using L{recent_performance.weeks_analyzed}W avg "
            f"({recent_performance.avg_points} pts)"
        )
    if projection_source == "recent_projection":
        return "Using recent projection avg"
    if projection_source == "recent_baseline":
        return "Using prior-week avg baseline"

    if flags:
        main_flag = flags[0].replace("_", " ")
        context = f"{main_flag}"
        if adjusted_value and adjusted_value != projection_value:
            diff = adjusted_value - projection_value
            sign = "+" if diff > 0 else ""
            context += f" ({sign}{diff:.1f} pts adj)"
        return context

    if recent_performance:
        return f"L{recent_performance.weeks_analyzed}W avg: {recent_performance.avg_points} pts"

    return "No recent performance data"


async def enrich_player(
    sleeper_id: str,
    include_adp: bool = True,
) -> EnhancedPlayer:
    """
    Full player enrichment pipeline: fetch data, resolve projection,
    calculate flags, optionally fetch ADP, and return EnhancedPlayer.

    This is the single source of truth for building an EnhancedPlayer object.
    """
    client = get_sleeper_client()
    settings = get_settings()
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    player_data = await client.get_player(sleeper_id)
    if not player_data:
        return None

    player = PlayerBase(**player_data)
    on_bye = player.bye_week == current_week

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, current_season, current_week
    )
    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Resolve projection through fallback chain
    projection_value, projection_source = await resolve_projection(
        client, sleeper_id, current_season, current_week,
        recent_performance, on_bye,
    )

    # Calculate flags and adjusted projection
    flags = []
    adjusted_value = None
    if recent_performance and not on_bye and projection_value > 0:
        engine = get_enhancement_engine()
        flags = engine.calculate_flags(projection_value, recent_performance)
        if flags:
            adjusted_value = engine.calculate_adjusted_projection(
                projection_value, recent_performance, flags
            )

    projection = PlayerProjection(
        sleeper_projection=projection_value,
        adjusted_projection=adjusted_value,
    )

    context = build_context_message(
        on_bye, player.bye_week, projection_source,
        flags, projection_value, adjusted_value, recent_performance,
    )

    # ADP / draft value (optional — skipped for comparison and pulse)
    draft_value_model = None
    if include_adp:
        adp_service = get_adp_service()
        adp_data = await adp_service.get_player_adp(
            player_name=player.name,
            year=settings.nfl_season,
            teams=12,
            scoring="ppr",
        )
        if adp_data and adp_data.get("adp"):
            adp_val = float(adp_data.get("adp", 0))
            draft_calc = calculate_draft_value(
                adp=adp_val,
                position=player.position,
                projection=projection_value,
            )
            std_dev = float(adp_data.get("stdev", 0)) if adp_data.get("stdev") else None
            high_pick = int(adp_data.get("high", 0)) if adp_data.get("high") else None
            low_pick = int(adp_data.get("low", 0)) if adp_data.get("low") else None
            draft_range = f"{high_pick}-{low_pick}" if high_pick and low_pick else None
            draft_value_model = DraftValue(
                adp=adp_val,
                adp_round=draft_calc.get("adp_round"),
                position_rank=draft_calc.get("position_rank"),
                value_tier=draft_calc.get("value_tier"),
                draft_flags=draft_calc.get("draft_flags", []),
                std_dev=std_dev,
                draft_range=draft_range,
            )

    return EnhancedPlayer(
        player=player,
        projection=projection,
        recent_performance=recent_performance,
        performance_flags=flags,
        context_message=context,
        on_bye=on_bye,
        draft_value=draft_value_model,
    )


async def enrich_player_for_comparison(
    sleeper_id: str,
) -> Optional[dict]:
    """
    Lighter enrichment for head-to-head comparison.
    Returns a dict with player, projection, flags, recent_performance
    needed by the comparison endpoint (no ADP, no context message).
    """
    client = get_sleeper_client()
    settings = get_settings()
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    player_data = await client.get_player(sleeper_id)
    if not player_data:
        return None

    player = PlayerBase(**player_data)

    proj_val = await client.get_player_projection(
        sleeper_id, current_season, current_week
    )

    perf_data = await client.get_recent_performance(
        sleeper_id, current_season, current_week, lookback=3
    )
    perf = (
        RecentPerformance(**perf_data)
        if perf_data and perf_data.get("weeks_analyzed", 0) > 0
        else None
    )

    engine = get_enhancement_engine()
    flags = engine.calculate_flags(proj_val, perf) if perf else []

    enhanced = EnhancedPlayer(
        player=player,
        projection=PlayerProjection(
            sleeper_projection=proj_val,
            adjusted_projection=(
                engine.calculate_adjusted_projection(proj_val, perf, flags)
                if perf else proj_val
            ),
            adjustment_reason=" ".join(flags) if flags else None,
        ),
        recent_performance=perf,
        performance_flags=flags,
        context_message="",
        on_bye=False,
    )

    return {
        "player": player,
        "enhanced": enhanced,
        "projection_value": proj_val,
        "perf": perf,
        "flags": flags,
    }
