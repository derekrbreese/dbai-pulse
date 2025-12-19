"""
Players router for dbAI Pulse API.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from services.sleeper import get_sleeper_client
from models.schemas import (
    PlayerSearchResult,
    EnhancedPlayer,
    PlayerBase,
    PlayerProjection,
    RecentPerformance,
)

router = APIRouter()


@router.get("/search", response_model=List[PlayerSearchResult])
async def search_players(
    q: str = Query(..., min_length=2, description="Player name to search for"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
):
    """
    Search for NFL players by name.
    Returns matching players with basic info.
    """
    client = get_sleeper_client()
    results = await client.search_players(q, limit=limit)
    return results


@router.get("/{sleeper_id}", response_model=EnhancedPlayer)
async def get_player(sleeper_id: str):
    """
    Get enhanced player data including projections and recent performance.
    """
    client = get_sleeper_client()
    settings = get_settings()

    # Get base player info
    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PlayerBase(**player_data)

    # Check bye week
    on_bye = player.bye_week == settings.nfl_week

    # Get projection
    projection_value = 0.0
    if not on_bye:
        projection_value = await client.get_player_projection(
            sleeper_id, settings.nfl_season, settings.nfl_week
        )

    projection = PlayerProjection(
        sleeper_projection=projection_value,
        adjusted_projection=None,  # Will be calculated by enhancement service
    )

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, settings.nfl_season, settings.nfl_week
    )

    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Build context message
    context = ""
    if on_bye:
        context = f"Player is on bye (Week {player.bye_week})"
    elif recent_performance:
        context = f"L{recent_performance.weeks_analyzed}W avg: {recent_performance.avg_points} pts"
    else:
        context = "No recent performance data"

    return EnhancedPlayer(
        player=player,
        projection=projection,
        recent_performance=recent_performance,
        performance_flags=[],  # Will be populated by enhancement service
        context_message=context,
        on_bye=on_bye,
    )


@router.get("/{sleeper_id}/trends")
async def get_player_trends(sleeper_id: str, lookback: int = Query(3, ge=1, le=8)):
    """
    Get trend data for charting (L3W or custom lookback).
    """
    client = get_sleeper_client()
    settings = get_settings()

    # Verify player exists
    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get weekly data
    weekly_data = []
    for i in range(1, lookback + 1):
        week = settings.nfl_week - i
        if week < 1:
            break

        stats = await client.get_player_stats(sleeper_id, settings.nfl_season, week)
        projection = await client.get_player_projection(
            sleeper_id, settings.nfl_season, week
        )

        points = 0.0
        if stats:
            points = stats.get("pts_ppr") or stats.get("pts") or 0.0

        weekly_data.append(
            {
                "week": week,
                "actual_points": round(points, 1),
                "projected_points": round(projection, 1),
            }
        )

    # Reverse so it's chronological
    weekly_data.reverse()

    return {
        "player_id": sleeper_id,
        "player_name": player_data["name"],
        "weeks": weekly_data,
    }
