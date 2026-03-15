"""
Players router for dbAI Pulse API.

Core player endpoints: search, enhanced detail, trends, ADP.
See also: pulse.py, comparison.py, flags.py for specialized endpoints.
"""

import asyncio
from typing import List

from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from models.schemas import (
    EnhancedPlayer,
    PlayerADP,
    PlayerADPResponse,
    PlayerSearchResult,
)
from services.adp import get_adp_service
from services.player_enrichment import enrich_player
from services.sleeper import get_sleeper_client

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
    enhanced = await enrich_player(sleeper_id, include_adp=True)
    if not enhanced:
        raise HTTPException(status_code=404, detail="Player not found")
    return enhanced


@router.get("/{sleeper_id}/trends")
async def get_player_trends(sleeper_id: str, lookback: int = Query(3, ge=1, le=8)):
    """
    Get trend data for charting (L3W or custom lookback).
    """
    client = get_sleeper_client()
    settings = get_settings()
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    weeks_to_fetch = [current_week - i for i in range(1, lookback + 1) if current_week - i >= 1]

    async def _fetch_week(week):
        stats, projection = await asyncio.gather(
            client.get_player_stats(sleeper_id, current_season, week),
            client.get_player_projection(sleeper_id, current_season, week),
        )
        points = 0.0
        if stats:
            stat_data = stats.get("stats", stats)
            points = stat_data.get("pts_ppr") or stat_data.get("pts") or 0.0
        return {"week": week, "actual_points": round(points, 1), "projected_points": round(projection, 1)}

    weekly_data = await asyncio.gather(*[_fetch_week(w) for w in weeks_to_fetch])
    weekly_data = sorted(weekly_data, key=lambda x: x["week"])

    return {
        "player_id": sleeper_id,
        "player_name": player_data["name"],
        "weeks": weekly_data,
    }


@router.get("/{sleeper_id}/adp", response_model=PlayerADPResponse)
async def get_player_adp(
    sleeper_id: str,
    scoring: str = Query("ppr", description="Scoring format: ppr, standard, half-ppr"),
    teams: int = Query(12, ge=8, le=16, description="League size"),
):
    """Get ADP (Average Draft Position) data for a player."""
    client = get_sleeper_client()
    adp_service = get_adp_service()
    settings = get_settings()

    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    player_name = player_data["name"]

    adp_data = await adp_service.get_player_adp(
        player_name=player_name,
        year=settings.nfl_season,
        teams=teams,
        scoring=scoring,
    )

    adp_model = None
    if adp_data:
        adp_model = PlayerADP(
            name=adp_data.get("name", player_name),
            position=adp_data.get("position", player_data.get("position", "")),
            adp=float(adp_data.get("adp", 0)),
            adp_round=float(adp_data.get("adp_round", 0)) if adp_data.get("adp_round") else None,
            std_dev=float(adp_data.get("stdev", 0)) if adp_data.get("stdev") else None,
            high=int(adp_data.get("high", 0)) if adp_data.get("high") else None,
            low=int(adp_data.get("low", 0)) if adp_data.get("low") else None,
            times_drafted=int(adp_data.get("times_drafted", 0)) if adp_data.get("times_drafted") else None,
        )

    return PlayerADPResponse(
        player_name=player_name,
        adp_data=adp_model,
        scoring=scoring,
        teams=teams,
        year=settings.nfl_season,
    )
