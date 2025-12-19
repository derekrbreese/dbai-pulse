"""
Gemini 3 Flash synthesis service for dbAI Pulse.
Uses Google's new genai SDK to synthesize fantasy football insights.
"""

import logging
import json
from typing import Dict, List, Optional
import os
from google import genai
from google.genai import types

from config import get_settings
from models.schemas import RecentPerformance

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiSynthesis:
    """Service for synthesizing fantasy football insights using Gemini 3 Flash."""

    MODEL_NAME = "gemini-3-flash-preview"  # Gemini 3 Flash Preview

    @staticmethod
    def create_synthesis_prompt(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        youtube_context: str,
    ) -> str:
        """
        Create a synthesis prompt for Gemini.

        Args:
            player_name: Player full name
            position: Position (QB, RB, WR, TE)
            projection: Projected points
            recent_performance: L3W performance data
            flags: Performance flags
            youtube_context: Summarized YouTube expert takes

        Returns:
            Formatted prompt string
        """
        # Build performance summary
        perf_summary = "No recent data available"
        if recent_performance:
            perf_summary = f"""
- L{recent_performance.weeks_analyzed}W Average: {recent_performance.avg_points} pts
- Best Week: {recent_performance.total_points / recent_performance.weeks_analyzed if recent_performance.weeks_analyzed > 0 else 0:.1f} pts
- Trend: {recent_performance.trend}
- Weekly Points: {", ".join([str(p) for p in recent_performance.weekly_points])}
"""

        flags_str = ", ".join(flags) if flags else "None"

        prompt = f"""You are an expert fantasy football analyst. Analyze the following data for {player_name} ({position}) and provide actionable start/sit advice for this week.

STATISTICAL DATA:
- Projected Points: {projection} pts
{perf_summary}
- Performance Flags: {flags_str}

EXPERT ANALYSIS (from YouTube):
{youtube_context}

Based on this information, provide a JSON response with the following structure:
{{
    "recommendation": "START" | "SIT" | "FLEX",
    "conviction": "HIGH" | "MEDIUM-HIGH" | "MIXED" | "MEDIUM-LOW" | "LOW",
    "reasoning": "2-3 sentence explanation of your recommendation",
    "key_factors": ["factor 1", "factor 2", "factor 3"],
    "risk_level": "LOW" | "MODERATE" | "HIGH",
    "expert_consensus": "brief summary of what experts are saying"
}}

Guidelines:
- START: Confident weekly starter in most leagues
- SIT: Bench or avoid this week
- FLEX: Borderline play, depends on roster depth
- Be specific and actionable
- Consider matchups, role, and recent trends
- Flag any injury concerns or uncertainties

Respond ONLY with valid JSON, no markdown formatting."""

        return prompt

    @staticmethod
    async def synthesize_player_analysis(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        youtube_context: str,
    ) -> Dict:
        """
        Use Gemini 3 Flash to synthesize all data into actionable insights.

        Returns:
            Dictionary with recommendation, conviction, reasoning, etc.
        """
        try:
            # Create Gemini client
            client = genai.Client(api_key=settings.gemini_api_key)

            # Build prompt
            prompt_text = GeminiSynthesis.create_synthesis_prompt(
                player_name=player_name,
                position=position,
                projection=projection,
                recent_performance=recent_performance,
                flags=flags,
                youtube_context=youtube_context,
            )

            logger.info(f"Sending Gemini 3 Flash request for {player_name}")

            # Create content parts
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt_text)],
                ),
            ]

            # Configure generation (no tools needed for this use case)
            generate_content_config = types.GenerateContentConfig(
                temperature=0.7,  # Balanced creativity
                max_output_tokens=1024,  # Enough for JSON response
            )

            # Generate response (non-streaming for simpler JSON parsing)
            response = client.models.generate_content(
                model=GeminiSynthesis.MODEL_NAME,
                contents=contents,
                config=generate_content_config,
            )

            # Extract text from response
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = (
                    response_text.replace("```json", "").replace("```", "").strip()
                )
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()

            result = json.loads(response_text)

            logger.info(
                f"Gemini synthesis complete for {player_name}: {result.get('recommendation')}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(
                f"Response text: {response_text if 'response_text' in locals() else 'N/A'}"
            )

            # Return fallback response
            return {
                "recommendation": "FLEX",
                "conviction": "LOW",
                "reasoning": "Unable to generate analysis due to parsing error.",
                "key_factors": ["Analysis unavailable"],
                "risk_level": "MODERATE",
                "expert_consensus": "No consensus available",
            }

        except Exception as e:
            logger.error(f"Error in Gemini synthesis for {player_name}: {e}")

            # Return fallback response
            return {
                "recommendation": "FLEX",
                "conviction": "LOW",
                "reasoning": f"Error generating analysis: {str(e)}",
                "key_factors": ["Analysis error"],
                "risk_level": "HIGH",
                "expert_consensus": "Unable to fetch expert opinions",
            }


def get_gemini_service() -> GeminiSynthesis:
    """Get Gemini synthesis service instance."""
    return GeminiSynthesis()
