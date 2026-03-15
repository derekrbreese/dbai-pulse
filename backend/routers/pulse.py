"""
Pulse analysis router — AI-powered player synthesis.

Combines Sleeper projections, YouTube expert takes, and Gemini AI
into a single actionable analysis.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import (
    ExpertTake,
    GeminiAnalysis,
    PulseResult,
)
from services.player_enrichment import enrich_player
from services.season_context import resolve_season_context
from services.storage import get_storage
from services.youtube import get_youtube_service
from services.gemini_synthesis import get_gemini_service

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/{sleeper_id}/pulse", response_model=PulseResult)
@limiter.limit("5/minute")
async def get_player_pulse(request: Request, sleeper_id: str):
    """
    Get full 'Pulse' analysis combining Sleeper data + YouTube experts + Gemini AI.

    This is the differentiator feature that synthesizes:
    - Sleeper projections and recent performance
    - Expert takes from YouTube fantasy football content
    - AI-powered analysis from Gemini 3.0 Flash
    """
    # Resolve current season context
    season, week, season_type = await resolve_season_context()

    # Reuse the shared enrichment pipeline (no ADP needed for pulse)
    enhanced_player = await enrich_player(sleeper_id, include_adp=False)
    if not enhanced_player:
        raise HTTPException(status_code=404, detail="Player not found")

    player = enhanced_player.player
    projection_value = enhanced_player.projection.sleeper_projection
    recent_performance = enhanced_player.recent_performance
    flags = enhanced_player.performance_flags

    # Search YouTube for expert takes on this player
    youtube_service = get_youtube_service()
    mentioned_sources = []
    not_mentioned_sources = []
    youtube_context_parts = []

    video_results = youtube_service.search_videos(
        player_name=player.name,
        max_results=5,
        days_back=90,
    )

    async def _process_video(video):
        """Fetch transcript and extract mentions for a single video concurrently."""
        transcript = await asyncio.to_thread(
            youtube_service.get_transcript, video["video_id"]
        )
        if not transcript:
            return None, video["channel_name"]
        mentions = youtube_service.extract_player_mentions(transcript, player.name)
        if not mentions:
            return None, video["channel_name"]
        video_context = youtube_service.summarize_for_gemini(
            mentions, max_length=500
        )
        return f"[{video['channel_name']}]: {video_context}", video["channel_name"]

    results = await asyncio.gather(
        *[_process_video(v) for v in video_results[:3]]
    )

    for context_text, channel_name in results:
        if context_text:
            youtube_context_parts.append(context_text)
            mentioned_sources.append(channel_name)
        else:
            not_mentioned_sources.append(channel_name)

    if youtube_context_parts:
        youtube_context = "\n\n---\n\n".join(youtube_context_parts)
    else:
        youtube_context = ""

    # Use Gemini to synthesize everything (including YouTube transcripts)
    adjusted_projection = enhanced_player.projection.adjusted_projection
    gemini_service = get_gemini_service()
    gemini_result = await gemini_service.synthesize_player_analysis(
        player_name=player.name,
        position=player.position,
        projection=projection_value,
        recent_performance=recent_performance,
        flags=flags,
        youtube_context=youtube_context,
        youtube_sources=mentioned_sources if mentioned_sources else None,
        season=season,
        week=week,
        season_type=season_type,
        adjusted_projection=adjusted_projection,
        team=player.team,
        bye_week=player.bye_week,
        on_bye=bool(player.bye_week and week and player.bye_week == week),
    )

    gemini_analysis = GeminiAnalysis(**gemini_result)

    # Log prediction for calibration tracking (fire-and-forget, never breaks Pulse)
    try:
        storage = get_storage()
        storage.log_prediction(
            sleeper_id=sleeper_id,
            player_name=player.name,
            position=player.position,
            season=season,
            week=week,
            recommendation=gemini_analysis.recommendation,
            conviction=gemini_analysis.conviction,
            risk_level=gemini_analysis.risk_level,
            projected_points=projection_value,
        )
    except Exception as e:
        logger.warning(f"Failed to log prediction for calibration: {e}")

    # Build expert takes using Gemini-generated summaries instead of raw transcript
    source_summaries = gemini_result.get("expert_source_summaries", {})
    expert_takes = []
    for source_name in mentioned_sources:
        summary = source_summaries.get(source_name)
        expert_takes.append(
            ExpertTake(
                source=source_name,
                reasoning=summary or "Discussed this player in recent video.",
                mentioned=True,
            )
        )
    for source_name in not_mentioned_sources:
        expert_takes.append(
            ExpertTake(source=source_name, mentioned=False)
        )

    return PulseResult(
        player=enhanced_player,
        gemini_analysis=gemini_analysis,
        youtube_context=youtube_context or f"No recent expert analysis found for {player.name}.",
        expert_takes=expert_takes,
        reddit_sentiment=None,
        season=season,
        week=week,
        season_type=season_type,
    )
