"""
Players router for dbAI Pulse API.
"""

from typing import List
from fastapi import APIRouter, HTTPException, Query

from config import get_settings
from services.sleeper import get_sleeper_client
from services.enhancement import get_enhancement_engine
from services.youtube import get_youtube_service
from services.gemini_synthesis import get_gemini_service
from models.schemas import (
    PlayerSearchResult,
    EnhancedPlayer,
    PlayerBase,
    PlayerProjection,
    RecentPerformance,
    PulseResult,
    GeminiAnalysis,
    ComparisonResult,
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

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, settings.nfl_season, settings.nfl_week
    )

    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Fallback: use L3W avg as projection if Sleeper returns 0
    # This happens during off-season or for past weeks
    is_projection_fallback = False
    if projection_value == 0 and recent_performance:
        projection_value = recent_performance.avg_points
        is_projection_fallback = True

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
        sleeper_projection=projection_value, adjusted_projection=adjusted_value
    )

    # Build context message
    context = ""
    if on_bye:
        context = f"Player is on bye (Week {player.bye_week})"
    elif is_projection_fallback:
        context = f"Using L3W avg ({recent_performance.avg_points} pts)"
    elif flags:
        # Prioritize important flags for context
        main_flag = flags[0].replace("_", " ")
        context = f"{main_flag}"
        if adjusted_value and adjusted_value != projection_value:
            diff = adjusted_value - projection_value
            sign = "+" if diff > 0 else ""
            context += f" ({sign}{diff:.1f} pts adj)"
    elif recent_performance:
        context = f"L{recent_performance.weeks_analyzed}W avg: {recent_performance.avg_points} pts"
    else:
        context = "No recent performance data"

    return EnhancedPlayer(
        player=player,
        projection=projection,
        recent_performance=recent_performance,
        performance_flags=flags,
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


@router.get("/{sleeper_id}/pulse", response_model=PulseResult)
async def get_player_pulse(sleeper_id: str):
    """
    Get full 'Pulse' analysis combining Sleeper data + YouTube experts + Gemini AI.

    This is the differentiator feature that synthesizes:
    - Sleeper projections and recent performance
    - Expert takes from YouTube fantasy football content
    - AI-powered analysis from Gemini 3.0 Flash
    """
    client = get_sleeper_client()
    settings = get_settings()

    # Get base player data (reuse existing endpoint logic)
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

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, settings.nfl_season, settings.nfl_week
    )

    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Fallback: use L3W avg as projection if Sleeper returns 0
    is_projection_fallback = False
    if projection_value == 0 and recent_performance:
        projection_value = recent_performance.avg_points
        is_projection_fallback = True

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
        sleeper_projection=projection_value, adjusted_projection=adjusted_value
    )

    # Build context message
    context = ""
    if on_bye:
        context = f"Player is on bye (Week {player.bye_week})"
    elif is_projection_fallback:
        context = f"Using L3W avg ({recent_performance.avg_points} pts)"
    elif flags:
        main_flag = flags[0].replace("_", " ")
        context = f"{main_flag}"
        if adjusted_value and adjusted_value != projection_value:
            diff = adjusted_value - projection_value
            sign = "+" if diff > 0 else ""
            context += f" ({sign}{diff:.1f} pts adj)"
    elif recent_performance:
        context = f"L{recent_performance.weeks_analyzed}W avg: {recent_performance.avg_points} pts"
    else:
        context = "No recent performance data"

    # Create enhanced player object
    enhanced_player = EnhancedPlayer(
        player=player,
        projection=projection,
        recent_performance=recent_performance,
        performance_flags=flags,
        context_message=context,
        on_bye=on_bye,
    )

    # For MVP: Use hardcoded YouTube video IDs (we'll add search later)
    # These are popular fantasy football analysis videos
    youtube_service = get_youtube_service()

    # Example video IDs - replace with actual search results in production
    sample_video_ids = [
        "dQw4w9WgXcQ",  # Placeholder - will be replaced with real search
    ]

    # Fetch transcripts and extract player mentions
    youtube_context = ""
    for video_id in sample_video_ids[:1]:  # Start with 1 video for MVP
        transcript = youtube_service.get_transcript(video_id)
        if transcript:
            mentions = youtube_service.extract_player_mentions(transcript, player.name)
            youtube_context = youtube_service.summarize_for_gemini(mentions)
            break

    # If no YouTube context, use placeholder
    if not youtube_context:
        youtube_context = f"No recent expert analysis found for {player.name}. Analysis based on statistical data only."

    # Use Gemini to synthesize everything
    gemini_service = get_gemini_service()

    gemini_result = await gemini_service.synthesize_player_analysis(
        player_name=player.name,
        position=player.position,
        projection=projection_value,
        recent_performance=recent_performance,
        flags=flags,
        youtube_context=youtube_context,
    )

    # Create Gemini analysis model
    gemini_analysis = GeminiAnalysis(**gemini_result)

    # Build final Pulse result
    return PulseResult(
        player=enhanced_player,
        gemini_analysis=gemini_analysis,
        youtube_context=youtube_context,
        expert_takes=[],  # Will populate in future iterations
        reddit_sentiment=None,  # Will add Reddit in Phase 4.2
    )


@router.get("/compare/{player_a_id}/{player_b_id}", response_model=ComparisonResult)
async def compare_players(player_a_id: str, player_b_id: str):
    """
    Compare two players head-to-head using Gemini with Google Search.
    Returns winner recommendation with reasoning.
    """
    client = get_sleeper_client()
    engine = get_enhancement_engine()
    gemini_service = get_gemini_service()

    # Fetch both players
    player_a = await client.get_player_by_id(player_a_id)
    player_b = await client.get_player_by_id(player_b_id)

    if not player_a or not player_b:
        raise HTTPException(status_code=404, detail="One or both players not found")

    # Get enhanced data for both
    proj_a = await client.get_player_projection(player_a_id)
    proj_b = await client.get_player_projection(player_b_id)

    stats_a = await client.get_player_stats_last_n_weeks(player_a_id, weeks=3)
    stats_b = await client.get_player_stats_last_n_weeks(player_b_id, weeks=3)

    # Calculate projections and performance
    proj_a_val = proj_a.get("pts_ppr", 0) if proj_a else 0
    proj_b_val = proj_b.get("pts_ppr", 0) if proj_b else 0

    perf_a = engine.calculate_recent_performance(stats_a)
    perf_b = engine.calculate_recent_performance(stats_b)

    flags_a = engine.calculate_flags(perf_a, proj_a_val, player_a.position)
    flags_b = engine.calculate_flags(perf_b, proj_b_val, player_b.position)

    # Get Gemini comparison
    comparison = await gemini_service.compare_players(
        player_a_name=player_a.name,
        player_a_position=player_a.position,
        player_a_projection=proj_a_val,
        player_a_avg=perf_a.avg_points if perf_a else 0,
        player_a_trend=perf_a.trend if perf_a else "unknown",
        player_a_flags=flags_a,
        player_b_name=player_b.name,
        player_b_position=player_b.position,
        player_b_projection=proj_b_val,
        player_b_avg=perf_b.avg_points if perf_b else 0,
        player_b_trend=perf_b.trend if perf_b else "unknown",
        player_b_flags=flags_b,
    )

    # Build enhanced player objects
    enhanced_a = EnhancedPlayer(
        player=player_a,
        projection=PlayerProjection(
            sleeper_projection=proj_a_val,
            adjusted_projection=engine.calculate_adjusted_projection(
                proj_a_val, perf_a, flags_a
            ),
            adjustment_reason=" ".join(flags_a) if flags_a else None,
        ),
        recent_performance=perf_a,
        performance_flags=flags_a,
        context_message=None,
        on_bye=False,
    )

    enhanced_b = EnhancedPlayer(
        player=player_b,
        projection=PlayerProjection(
            sleeper_projection=proj_b_val,
            adjusted_projection=engine.calculate_adjusted_projection(
                proj_b_val, perf_b, flags_b
            ),
            adjustment_reason=" ".join(flags_b) if flags_b else None,
        ),
        recent_performance=perf_b,
        performance_flags=flags_b,
        context_message=None,
        on_bye=False,
    )

    winner_name = (
        player_a.name
        if comparison["winner"] == "A"
        else (player_b.name if comparison["winner"] == "B" else "Toss-up")
    )

    return ComparisonResult(
        player_a=enhanced_a,
        player_b=enhanced_b,
        winner=comparison["winner"],
        winner_name=winner_name,
        conviction=comparison["conviction"],
        reasoning=comparison["reasoning"],
        key_advantages_a=comparison["key_advantages_a"],
        key_advantages_b=comparison["key_advantages_b"],
        matchup_edge=comparison["matchup_edge"],
        sources_used=comparison["sources_used"],
    )
