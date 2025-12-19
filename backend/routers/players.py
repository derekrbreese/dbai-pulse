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
