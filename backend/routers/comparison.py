"""
Player comparison router — head-to-head analysis via Gemini + Google Search.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import ComparisonResult
from services.gemini_synthesis import get_gemini_service
from services.player_enrichment import enrich_player_for_comparison
from services.season_context import resolve_season_context

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/compare/{player_a_id}/{player_b_id}", response_model=ComparisonResult)
@limiter.limit("10/minute")
async def compare_players(request: Request, player_a_id: str, player_b_id: str):
    """
    Compare two players head-to-head using Gemini with Google Search.
    Returns winner recommendation with reasoning.
    """
    gemini_service = get_gemini_service()

    # Resolve current season context
    season, week, season_type = await resolve_season_context()

    logger.info(f"Comparing players {player_a_id} vs {player_b_id}")

    data_a = await enrich_player_for_comparison(player_a_id)
    data_b = await enrich_player_for_comparison(player_b_id)

    if not data_a or not data_b:
        raise HTTPException(status_code=404, detail="One or both players not found")

    logger.info(
        f"Found players: {data_a['player'].name} vs {data_b['player'].name}"
    )

    proj_a = (
        data_a["enhanced"].projection.adjusted_projection
        or data_a["projection_value"]
    )
    proj_b = (
        data_b["enhanced"].projection.adjusted_projection
        or data_b["projection_value"]
    )

    comparison = await gemini_service.compare_players(
        player_a_name=data_a["player"].name,
        player_a_position=data_a["player"].position,
        player_a_projection=proj_a,
        player_a_avg=data_a["perf"].avg_points if data_a["perf"] else 0,
        player_a_trend=data_a["perf"].trend if data_a["perf"] else "unknown",
        player_a_flags=data_a["flags"],
        player_b_name=data_b["player"].name,
        player_b_position=data_b["player"].position,
        player_b_projection=proj_b,
        player_b_avg=data_b["perf"].avg_points if data_b["perf"] else 0,
        player_b_trend=data_b["perf"].trend if data_b["perf"] else "unknown",
        player_b_flags=data_b["flags"],
        season=season,
        week=week,
        season_type=season_type,
    )

    logger.info(f"Gemini returned winner: {comparison.get('winner')}")

    winner_name = (
        data_a["player"].name
        if comparison["winner"] == "A"
        else (data_b["player"].name if comparison["winner"] == "B" else "Toss-up")
    )

    return ComparisonResult(
        player_a=data_a["enhanced"],
        player_b=data_b["enhanced"],
        winner=comparison["winner"],
        winner_name=winner_name,
        conviction=comparison["conviction"],
        reasoning=comparison["reasoning"],
        key_advantages_a=comparison["key_advantages_a"],
        key_advantages_b=comparison["key_advantages_b"],
        matchup_edge=comparison["matchup_edge"],
        sources_used=comparison["sources_used"],
        season=season,
        week=week,
        season_type=season_type,
    )
