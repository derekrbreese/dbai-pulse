"""
Yahoo Fantasy data router for dbAI Pulse API.
Endpoints for fetching user leagues, rosters, and customizable team insights.
"""

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from models.schemas import (
    RosterInsightsResponse,
    TeamFeedbackPreferences,
    TeamFeedbackPreferencesUpdate,
    WaiverWireResponse,
)
from routers.session_utils import get_authenticated_user_id
from services.roster_insights import get_roster_insights_service
from services.storage import get_storage
from services.yahoo import get_yahoo_service
from services.yahoo_token_manager import get_yahoo_token_manager

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_SCORING = "ppr"
DEFAULT_RISK = "balanced"
DEFAULT_FOCUS = "upside"


async def _get_authed_yahoo_context(
    request: Request,
) -> tuple[str, Dict[str, Any], Any, Any]:
    """Resolve request-scoped user id, valid token, and Yahoo service."""
    user_id = get_authenticated_user_id(request)
    token_manager = get_yahoo_token_manager()
    token_data = await token_manager.get_valid_token(user_id)
    yahoo_service = get_yahoo_service(token_data, user_id)
    return user_id, token_data, token_manager, yahoo_service


def _preferences_key(preferences: TeamFeedbackPreferences) -> str:
    """Build deterministic cache key from team preference values."""
    return f"{preferences.scoring}|{preferences.risk}|{preferences.focus}"


def _load_preferences(user_id: str, team_key: str) -> TeamFeedbackPreferences:
    """Load stored team preferences, falling back to defaults."""
    storage = get_storage()
    row = storage.get_team_preferences(user_id, team_key)
    if not row:
        return TeamFeedbackPreferences(
            scoring=DEFAULT_SCORING,
            risk=DEFAULT_RISK,
            focus=DEFAULT_FOCUS,
            updated_at=None,
        )

    return TeamFeedbackPreferences(
        scoring=row.get("scoring", DEFAULT_SCORING),
        risk=row.get("risk", DEFAULT_RISK),
        focus=row.get("focus", DEFAULT_FOCUS),
        updated_at=row.get("updated_at"),
    )


def _merge_preference_overrides(
    base: TeamFeedbackPreferences,
    scoring: Optional[Literal["ppr", "half_ppr", "std"]],
    risk: Optional[Literal["conservative", "balanced", "aggressive"]],
    focus: Optional[Literal["floor", "upside", "ceiling"]],
) -> TeamFeedbackPreferences:
    """Apply optional query overrides to a base preference object."""
    return TeamFeedbackPreferences(
        scoring=scoring or base.scoring,
        risk=risk or base.risk,
        focus=focus or base.focus,
        updated_at=base.updated_at,
    )


async def _get_user_teams_with_metadata(yahoo_service: Any) -> list[Dict[str, Any]]:
    """Fetch user teams and enrich with league metadata."""
    teams = await yahoo_service.get_user_teams()

    try:
        leagues = await yahoo_service.get_user_leagues()
    except Exception as exc:
        logger.warning("Could not fetch leagues for team enrichment (%s), continuing without", exc)
        leagues = []

    leagues_by_key = {league.get("league_key"): league for league in leagues}

    enriched_teams = []
    for team in teams:
        league_key = team.get("league_key")
        league = leagues_by_key.get(league_key, {})

        enriched_teams.append(
            {
                "team_id": team.get("team_id"),
                "team_key": team.get("team_key"),
                "name": team.get("name"),
                "team_name": team.get("name"),
                "league_key": league_key,
                "league_name": league.get("name"),
                "season": league.get("season"),
            }
        )

    return enriched_teams


async def _compute_team_insights(
    request: Request,
    team_key: str,
    scoring: Optional[Literal["ppr", "half_ppr", "std"]] = None,
    risk: Optional[Literal["conservative", "balanced", "aggressive"]] = None,
    focus: Optional[Literal["floor", "upside", "ceiling"]] = None,
    refresh: bool = False,
) -> RosterInsightsResponse:
    """Shared implementation for insights and refresh endpoints."""
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)
    storage = get_storage()
    insights_service = get_roster_insights_service()

    teams = await _get_user_teams_with_metadata(yahoo_service)
    team = next((item for item in teams if item.get("team_key") == team_key), None)
    if not team:
        raise HTTPException(status_code=404, detail="Yahoo team not found for current user.")

    saved_preferences = _load_preferences(user_id, team_key)
    preferences = _merge_preference_overrides(saved_preferences, scoring, risk, focus)
    prefs_key = _preferences_key(preferences)

    if not refresh:
        cached_payload = storage.get_team_insights_cache(user_id, team_key, prefs_key)
        if cached_payload:
            cached_payload["cached"] = True
            token_manager.save_external_token(
                user_id=user_id,
                token_payload=yahoo_service.get_token_data(),
                existing_token=token_data,
            )
            return RosterInsightsResponse(**cached_payload)

    insights = await insights_service.generate_team_insights(
        yahoo_service=yahoo_service,
        user_id=user_id,
        team_summary=team,
        preferences=preferences,
    )
    payload = insights.model_dump()
    payload["cached"] = False

    storage.save_team_insights_cache(
        user_id=user_id,
        team_key=team_key,
        prefs_key=prefs_key,
        payload=payload,
        ttl_seconds=insights_service.settings.yahoo_cache_ttl_seconds,
    )

    token_manager.save_external_token(
        user_id=user_id,
        token_payload=yahoo_service.get_token_data(),
        existing_token=token_data,
    )
    return RosterInsightsResponse(**payload)


@router.get("/leagues")
async def get_user_leagues(
    request: Request,
    game_id: Optional[int] = Query(None, description="Yahoo game ID for specific season"),
):
    """
    Get user's Yahoo Fantasy football leagues.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    try:
        leagues = await yahoo_service.get_user_leagues(game_id)
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return {"leagues": leagues, "count": len(leagues)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch leagues: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/teams")
async def get_user_teams(request: Request):
    """
    Get all teams the user owns across leagues.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    try:
        teams = await _get_user_teams_with_metadata(yahoo_service)
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return {"teams": teams, "count": len(teams)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch teams: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/teams/{team_key}/preferences", response_model=TeamFeedbackPreferences)
async def get_team_preferences(request: Request, team_key: str):
    """
    Get saved feedback customization preferences for a team.
    """
    await _get_authed_yahoo_context(request)
    user_id = get_authenticated_user_id(request)
    return _load_preferences(user_id, team_key)


@router.put("/teams/{team_key}/preferences", response_model=TeamFeedbackPreferences)
async def update_team_preferences(
    request: Request,
    team_key: str,
    preferences: TeamFeedbackPreferencesUpdate,
):
    """
    Save feedback customization preferences for a team.
    """
    user_id, _, _, _ = await _get_authed_yahoo_context(request)
    storage = get_storage()
    updated_at = storage.save_team_preferences(
        user_id=user_id,
        team_key=team_key,
        scoring=preferences.scoring,
        risk=preferences.risk,
        focus=preferences.focus,
    )
    storage.clear_team_insights_cache(user_id, team_key=team_key)

    return TeamFeedbackPreferences(
        scoring=preferences.scoring,
        risk=preferences.risk,
        focus=preferences.focus,
        updated_at=updated_at,
    )


@router.get("/teams/{team_key}/insights", response_model=RosterInsightsResponse)
async def get_team_insights(
    request: Request,
    team_key: str,
    scoring: Optional[Literal["ppr", "half_ppr", "std"]] = Query(None),
    risk: Optional[Literal["conservative", "balanced", "aggressive"]] = Query(None),
    focus: Optional[Literal["floor", "upside", "ceiling"]] = Query(None),
    refresh: bool = Query(False, description="Bypass cache and recompute roster insights."),
):
    """
    Get customizable roster insights for one Yahoo team.
    """
    try:
        return await _compute_team_insights(
            request=request,
            team_key=team_key,
            scoring=scoring,
            risk=risk,
            focus=focus,
            refresh=refresh,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to build team insights: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/teams/{team_key}/insights/refresh", response_model=RosterInsightsResponse)
async def refresh_team_insights(
    request: Request,
    team_key: str,
):
    """
    Force refresh roster insights for one Yahoo team.
    """
    try:
        return await _compute_team_insights(
            request=request,
            team_key=team_key,
            refresh=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to refresh team insights: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/leagues/{league_key}/waivers", response_model=WaiverWireResponse)
async def get_waiver_wire(
    request: Request,
    league_key: str,
    position: Optional[str] = Query(None, description="Position filter (QB, RB, WR, TE, K)"),
    scoring: Literal["ppr", "half_ppr", "std"] = Query("ppr"),
    risk: Literal["conservative", "balanced", "aggressive"] = Query("balanced"),
    focus: Literal["floor", "upside", "ceiling"] = Query("upside"),
    count: int = Query(50, ge=1, le=100),
):
    """
    Get waiver wire intelligence for available free agents in a Yahoo league.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    # Resolve league name from teams data
    league_name = None
    try:
        teams = await _get_user_teams_with_metadata(yahoo_service)
        for team in teams:
            if team.get("league_key") == league_key:
                league_name = team.get("league_name")
                break
    except Exception:
        pass

    preferences = TeamFeedbackPreferences(scoring=scoring, risk=risk, focus=focus)
    insights_service = get_roster_insights_service()

    try:
        result = await insights_service.generate_waiver_insights(
            yahoo_service=yahoo_service,
            user_id=user_id,
            league_key=league_key,
            league_name=league_name,
            preferences=preferences,
            position=position,
            count=count,
        )
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to build waiver wire insights: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/leagues/{league_id}/roster/{team_id}")
async def get_team_roster(
    request: Request,
    league_id: str,
    team_id: str,
    week: Optional[int] = Query(None, description="Week number for historical roster"),
):
    """
    Get roster for a specific team in a league.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    try:
        roster = await yahoo_service.get_team_roster(league_id, team_id, week)
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return {
            "league_id": league_id,
            "team_id": team_id,
            "week": week,
            "roster": roster,
            "count": len(roster),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch roster: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/leagues/{league_id}/draft")
async def get_league_draft(request: Request, league_id: str):
    """
    Get draft results for a league.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    try:
        draft_results = await yahoo_service.get_league_draft_results(league_id)
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        return {
            "league_id": league_id,
            "picks": draft_results,
            "count": len(draft_results),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch draft results: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/player/{player_key}")
async def get_yahoo_player(
    request: Request,
    player_key: str,
    league_id: str = Query(..., description="League ID for context"),
):
    """
    Get Yahoo player details.
    """
    user_id, token_data, token_manager, yahoo_service = await _get_authed_yahoo_context(request)

    try:
        player = await yahoo_service.get_player_details(league_id, player_key)
        token_manager.save_external_token(
            user_id=user_id,
            token_payload=yahoo_service.get_token_data(),
            existing_token=token_data,
        )
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return player
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch player: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
