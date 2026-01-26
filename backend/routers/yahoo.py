"""
Yahoo Fantasy data router for dbAI Pulse API.
Endpoints for fetching user leagues, rosters, and draft data.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from services.yahoo import get_yahoo_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/leagues")
async def get_user_leagues(
    game_id: Optional[int] = Query(None, description="Yahoo game ID for specific season")
):
    """
    Get user's Yahoo Fantasy football leagues.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        leagues = await yahoo_service.get_user_leagues(game_id)
        return {"leagues": leagues, "count": len(leagues)}
    except Exception as e:
        logger.error(f"Failed to fetch leagues: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/teams")
async def get_user_teams():
    """
    Get all teams the user owns across leagues.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        teams = await yahoo_service.get_user_teams()
        return {"teams": teams, "count": len(teams)}
    except Exception as e:
        logger.error(f"Failed to fetch teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leagues/{league_id}/roster/{team_id}")
async def get_team_roster(
    league_id: str,
    team_id: str,
    week: Optional[int] = Query(None, description="Week number for historical roster")
):
    """
    Get roster for a specific team in a league.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        roster = await yahoo_service.get_team_roster(league_id, team_id, week)
        return {
            "league_id": league_id,
            "team_id": team_id,
            "week": week,
            "roster": roster,
            "count": len(roster)
        }
    except Exception as e:
        logger.error(f"Failed to fetch roster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leagues/{league_id}/draft")
async def get_league_draft(league_id: str):
    """
    Get draft results for a league.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        draft_results = await yahoo_service.get_league_draft_results(league_id)
        return {
            "league_id": league_id,
            "picks": draft_results,
            "count": len(draft_results)
        }
    except Exception as e:
        logger.error(f"Failed to fetch draft results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/player/{player_key}")
async def get_yahoo_player(
    player_key: str,
    league_id: str = Query(..., description="League ID for context")
):
    """
    Get Yahoo player details.
    """
    yahoo_service = get_yahoo_service()
    
    if not yahoo_service.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not connected to Yahoo. Please authenticate first."
        )
    
    try:
        player = await yahoo_service.get_player_details(league_id, player_key)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return player
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch player: {e}")
        raise HTTPException(status_code=500, detail=str(e))
