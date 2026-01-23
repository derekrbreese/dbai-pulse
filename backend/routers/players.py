"""
Players router for dbAI Pulse API.
"""

from typing import List, Optional
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
    ExpertTake,
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


# Valid flags for the browser
VALID_FLAGS = [
    "BREAKOUT_CANDIDATE",
    "TRENDING_UP",
    "UNDERPERFORMING",
    "DECLINING_ROLE",
    "HIGH_CEILING",
    "BOOM_BUST",
    "CONSISTENT",
]


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
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    print(f"[DEBUG] get_players_by_flag called with flag={flag}, position={position}")

    try:
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

        # Get pool of active players
        pool_size = min(2000, max(500, limit * 20))
        players = await client.get_active_players_by_position(
            position=position, limit=pool_size
        )

        print(f"[DEBUG] Checking {len(players)} players for flag {flag_upper}")
        logger.info(f"Checking {len(players)} players for flag {flag_upper}")

        matching_players = []

        for player_data in players:
            try:
                # Get projection and recent performance
                on_bye = player_data.get("bye_week") == current_week
                projection_value = 0.0
                if not on_bye:
                    projection_value = await client.get_player_projection(
                        player_data["sleeper_id"],
                        current_season,
                        current_week,
                    )

                perf_data = await client.get_recent_performance(
                    player_data["sleeper_id"],
                    current_season,
                    current_week,
                    lookback=3,
                )

                # Log first few players for debugging
                if len(matching_players) < 3:
                    logger.info(
                        f"Processing player {player_data['name']}: perf_data={perf_data}"
                    )

                # Skip players with no recent data
                if not perf_data or perf_data.get("weeks_analyzed", 0) == 0:
                    continue

                perf = RecentPerformance(**perf_data)

                # Fallback to recent projection avg, then prior-week avg, then L3W avg
                previous_avg = 0.0
                if len(perf.weekly_points) > 1:
                    previous_avg = sum(perf.weekly_points[1:]) / (
                        len(perf.weekly_points) - 1
                    )

                if projection_value == 0 and not on_bye:
                    projection_value = await client.get_recent_projection_avg(
                        player_data["sleeper_id"],
                        current_season,
                        current_week,
                        lookback=3,
                    )
                if projection_value == 0 and previous_avg > 0:
                    projection_value = round(previous_avg, 1)
                if projection_value == 0:
                    projection_value = perf.avg_points

                # Calculate flags
                flags = []
                if not on_bye and projection_value > 0:
                    flags = engine.calculate_flags(projection_value, perf)

                # Debug logging for first 5 players
                if len(matching_players) < 5 or flag_upper in flags:
                    logger.info(
                        f"Player: {player_data['name']}, proj={projection_value}, avg={perf.avg_points}, flags={flags}"
                    )

                # Check if this player has the target flag
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

        # Sort by avg points descending
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_players_by_flag: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flags/available")
async def get_available_flags():
    """Get list of available flags for the browser."""
    return {
        "flags": [
            {
                "id": "BREAKOUT_CANDIDATE",
                "label": "🚀 Breakout",
                "description": "L3W avg > 150% of projection",
            },
            {
                "id": "TRENDING_UP",
                "label": "📈 Trending Up",
                "description": "L3W avg > 120% of projection",
            },
            {
                "id": "UNDERPERFORMING",
                "label": "📉 Underperforming",
                "description": "L3W avg < 80% of projection",
            },
            {
                "id": "DECLINING_ROLE",
                "label": "⚠️ Declining",
                "description": "L3W avg < 70% of projection",
            },
            {
                "id": "HIGH_CEILING",
                "label": "🎯 High Ceiling",
                "description": "Best week > 200% of projection",
            },
            {
                "id": "BOOM_BUST",
                "label": "🎰 Boom/Bust",
                "description": "High variance player",
            },
            {
                "id": "CONSISTENT",
                "label": "✅ Consistent",
                "description": "Low variance, reliable",
            },
        ]
    }


@router.get("/{sleeper_id}", response_model=EnhancedPlayer)
async def get_player(sleeper_id: str):
    """
    Get enhanced player data including projections and recent performance.
    """
    client = get_sleeper_client()
    settings = get_settings()
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    # Get base player info
    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PlayerBase(**player_data)

    # Check bye week
    on_bye = player.bye_week == current_week

    # Get projection
    projection_value = 0.0
    if not on_bye:
        projection_value = await client.get_player_projection(
            sleeper_id, current_season, current_week
        )

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, current_season, current_week
    )

    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Fallback: use recent projection avg, then prior-week avg, then L3W avg
    # This happens during off-season or for past weeks
    projection_source = "sleeper"
    previous_avg = 0.0
    if recent_performance and len(recent_performance.weekly_points) > 1:
        previous_avg = sum(recent_performance.weekly_points[1:]) / (
            len(recent_performance.weekly_points) - 1
        )
    if projection_value == 0 and recent_performance:
        projection_value = await client.get_recent_projection_avg(
            sleeper_id, current_season, current_week, lookback=3
        )
        if projection_value > 0:
            projection_source = "recent_projection"
    if projection_value == 0 and previous_avg > 0:
        projection_value = round(previous_avg, 1)
        projection_source = "recent_baseline"
    if projection_value == 0 and recent_performance:
        projection_value = recent_performance.avg_points
        projection_source = "recent_avg"

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
    elif projection_source == "recent_avg":
        context = (
            f"Using L{recent_performance.weeks_analyzed}W avg "
            f"({recent_performance.avg_points} pts)"
        )
    elif projection_source == "recent_projection":
        context = "Using recent projection avg"
    elif projection_source == "recent_baseline":
        context = "Using prior-week avg baseline"
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
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    # Verify player exists
    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    # Get weekly data
    weekly_data = []
    for i in range(1, lookback + 1):
        week = current_week - i
        if week < 1:
            break

        stats = await client.get_player_stats(sleeper_id, current_season, week)
        projection = await client.get_player_projection(
            sleeper_id, current_season, week
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
    current_season, current_week = await client.get_current_season_week(
        settings.nfl_season, settings.nfl_week
    )

    # Get base player data (reuse existing endpoint logic)
    player_data = await client.get_player(sleeper_id)
    if not player_data:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PlayerBase(**player_data)

    # Check bye week
    on_bye = player.bye_week == current_week

    # Get projection
    projection_value = 0.0
    if not on_bye:
        projection_value = await client.get_player_projection(
            sleeper_id, current_season, current_week
        )

    # Get recent performance
    recent_data = await client.get_recent_performance(
        sleeper_id, current_season, current_week
    )

    recent_performance = None
    if recent_data["weeks_analyzed"] > 0:
        recent_performance = RecentPerformance(**recent_data)

    # Fallback: use recent projection avg, then prior-week avg, then L3W avg
    projection_source = "sleeper"
    previous_avg = 0.0
    if recent_performance and len(recent_performance.weekly_points) > 1:
        previous_avg = sum(recent_performance.weekly_points[1:]) / (
            len(recent_performance.weekly_points) - 1
        )
    if projection_value == 0 and recent_performance:
        projection_value = await client.get_recent_projection_avg(
            sleeper_id, current_season, current_week, lookback=3
        )
        if projection_value > 0:
            projection_source = "recent_projection"
    if projection_value == 0 and previous_avg > 0:
        projection_value = round(previous_avg, 1)
        projection_source = "recent_baseline"
    if projection_value == 0 and recent_performance:
        projection_value = recent_performance.avg_points
        projection_source = "recent_avg"

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
    elif projection_source == "recent_avg":
        context = (
            f"Using L{recent_performance.weeks_analyzed}W avg "
            f"({recent_performance.avg_points} pts)"
        )
    elif projection_source == "recent_projection":
        context = "Using recent projection avg"
    elif projection_source == "recent_baseline":
        context = "Using prior-week avg baseline"
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

    # Search YouTube for expert takes on this player
    youtube_service = get_youtube_service()
    expert_takes = []
    youtube_context_parts = []

    # Search for videos mentioning this player (curated channels first, then general)
    # Using 90 days to handle offseason testing
    video_results = youtube_service.search_videos(
        player_name=player.name,
        max_results=5,
        days_back=90,
    )

    # Fetch transcripts and extract player mentions
    for video in video_results[:3]:  # Limit to 3 videos for performance
        transcript = youtube_service.get_transcript(video["video_id"])
        if transcript:
            mentions = youtube_service.extract_player_mentions(transcript, player.name)
            if mentions:
                # Build context for Gemini
                video_context = youtube_service.summarize_for_gemini(
                    mentions, max_length=500
                )
                youtube_context_parts.append(
                    f"[{video['channel_name']}]: {video_context}"
                )

                # Create ExpertTake for UI with quote
                quote_text = mentions[0]["text"]
                if len(quote_text) > 200:
                    quote_text = quote_text[:200] + "..."

                expert_takes.append(
                    ExpertTake(
                        source=video["channel_name"],
                        reasoning=quote_text,
                        mentioned=True,
                    )
                )
            else:
                # Video exists but player not mentioned in transcript
                expert_takes.append(
                    ExpertTake(
                        source=video["channel_name"],
                        mentioned=False,
                    )
                )
        else:
            # No transcript available
            expert_takes.append(
                ExpertTake(
                    source=video["channel_name"],
                    mentioned=False,
                )
            )

    # Combine YouTube context for Gemini
    if youtube_context_parts:
        youtube_context = "\n\n---\n\n".join(youtube_context_parts)
    else:
        youtube_context = (
            f"No recent expert analysis found for {player.name}. "
            "Analysis based on statistical data only."
        )

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
        expert_takes=expert_takes,
        reddit_sentiment=None,  # Will add Reddit in Phase 4.2
    )


@router.get("/compare/{player_a_id}/{player_b_id}", response_model=ComparisonResult)
async def compare_players(player_a_id: str, player_b_id: str):
    """
    Compare two players head-to-head using Gemini with Google Search.
    Returns winner recommendation with reasoning.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        client = get_sleeper_client()
        engine = get_enhancement_engine()
        gemini_service = get_gemini_service()

        logger.info(f"Comparing players {player_a_id} vs {player_b_id}")

        # Fetch both players (returns dict, not object)
        player_a_data = await client.get_player(player_a_id)
        player_b_data = await client.get_player(player_b_id)

        if not player_a_data or not player_b_data:
            raise HTTPException(status_code=404, detail="One or both players not found")

        logger.info(
            f"Found players: {player_a_data.get('name')} vs {player_b_data.get('name')}"
        )

        # Convert to PlayerBase objects
        player_a = PlayerBase(**player_a_data)
        player_b = PlayerBase(**player_b_data)

        # Get settings for season/week
        settings = get_settings()
        current_season, current_week = await client.get_current_season_week(
            settings.nfl_season, settings.nfl_week
        )

        # Get enhanced data for both - need season and week
        proj_a_val = await client.get_player_projection(
            player_a_id, current_season, current_week
        )
        proj_b_val = await client.get_player_projection(
            player_b_id, current_season, current_week
        )

        # Get recent performance
        perf_a_data = await client.get_recent_performance(
            player_a_id, current_season, current_week, lookback=3
        )
        perf_b_data = await client.get_recent_performance(
            player_b_id, current_season, current_week, lookback=3
        )

        # Convert to RecentPerformance objects if data exists
        perf_a = (
            RecentPerformance(**perf_a_data)
            if perf_a_data and perf_a_data.get("weeks_analyzed", 0) > 0
            else None
        )
        perf_b = (
            RecentPerformance(**perf_b_data)
            if perf_b_data and perf_b_data.get("weeks_analyzed", 0) > 0
            else None
        )

        # calculate_flags expects (projection, recent_performance)
        flags_a = engine.calculate_flags(proj_a_val, perf_a) if perf_a else []
        flags_b = engine.calculate_flags(proj_b_val, perf_b) if perf_b else []

        logger.info(f"Calling Gemini compare_players...")

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

        logger.info(f"Gemini returned winner: {comparison.get('winner')}")

        # Build enhanced player objects
        enhanced_a = EnhancedPlayer(
            player=player_a,
            projection=PlayerProjection(
                sleeper_projection=proj_a_val,
                adjusted_projection=engine.calculate_adjusted_projection(
                    proj_a_val, perf_a, flags_a
                )
                if perf_a
                else proj_a_val,
                adjustment_reason=" ".join(flags_a) if flags_a else None,
            ),
            recent_performance=perf_a,
            performance_flags=flags_a,
            context_message="",
            on_bye=False,
        )

        enhanced_b = EnhancedPlayer(
            player=player_b,
            projection=PlayerProjection(
                sleeper_projection=proj_b_val,
                adjusted_projection=engine.calculate_adjusted_projection(
                    proj_b_val, perf_b, flags_b
                )
                if perf_b
                else proj_b_val,
                adjustment_reason=" ".join(flags_b) if flags_b else None,
            ),
            recent_performance=perf_b,
            performance_flags=flags_b,
            context_message="",
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
    except Exception as e:
        logger.error(f"Error in compare_players: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
