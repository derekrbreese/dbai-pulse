"""
Gemini 3 Flash synthesis service for dbAI Pulse.
Uses Google's genai SDK with Google Search grounding for real-time fantasy insights.
"""

import logging
import json
import re
from typing import Dict, List, Optional
from google import genai
from google.genai import types

from config import get_settings
from models.schemas import RecentPerformance

logger = logging.getLogger(__name__)
settings = get_settings()


class GeminiSynthesis:
    """Service for synthesizing fantasy football insights using Gemini 3 Flash with Google Search."""

    MODEL_NAME = "gemini-3-flash-preview"  # Gemini 3 Flash Preview

    @staticmethod
    def _extract_json(text: str) -> Dict:
        """
        Robustly extract JSON from Gemini response text.
        Handles markdown blocks, extra text, and malformed responses.
        """
        # First, try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object by looking for { ... }
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # If all else fails, try parsing the whole thing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Could not extract JSON from response: {text[:200]}...")
            raise

    @staticmethod
    def create_synthesis_prompt(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
    ) -> str:
        """
        Create a synthesis prompt for Gemini with Google Search grounding.
        """
        # Build performance summary
        perf_summary = "No recent data available"
        if recent_performance:
            perf_summary = f"""
- L{recent_performance.weeks_analyzed}W Average: {recent_performance.avg_points} pts
- Trend: {recent_performance.trend}
- Weekly Points: {", ".join([str(p) for p in recent_performance.weekly_points])}
"""

        flags_str = ", ".join(flags) if flags else "None"

        prompt = f"""You are an expert fantasy football analyst helping with Week 16 of the 2025 NFL season.

PLAYER: {player_name} ({position})

STATISTICAL DATA FROM SLEEPER API:
- Projected Points: {projection} pts
{perf_summary}
- Performance Flags: {flags_str}

YOUR TASK:
1. Use Google Search to find the LATEST news, injury updates, and expert opinions about {player_name} for this week
2. Look for recent Reddit discussions, Twitter/X posts, and fantasy analyst takes
3. Check for any breaking news that affects their value
4. Consider their matchup this week

Based on ALL available information (stats + live search results), provide a JSON response:
{{
    "recommendation": "START" | "SIT" | "FLEX",
    "conviction": "HIGH" | "MEDIUM-HIGH" | "MIXED" | "MEDIUM-LOW" | "LOW",
    "reasoning": "2-3 sentence explanation citing specific sources you found",
    "key_factors": ["factor 1 with source", "factor 2 with source", "factor 3 with source"],
    "risk_level": "LOW" | "MODERATE" | "HIGH",
    "expert_consensus": "summary of what fantasy experts are saying, cite sources",
    "sources_used": ["source 1", "source 2", "source 3"]
}}

IMPORTANT: 
- Cite specific sources you find (e.g., "FantasyPros ranks him...", "Reddit r/fantasyfootball says...")
- Include any injury news or matchup concerns
- Be specific about THIS WEEK's outlook

Respond ONLY with valid JSON, no markdown formatting."""

        return prompt

    @staticmethod
    async def synthesize_player_analysis(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        youtube_context: str = "",  # Kept for backwards compatibility
    ) -> Dict:
        """
        Use Gemini 3 Flash with Google Search grounding to synthesize insights.
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
            )

            logger.info(
                f"Sending Gemini 3 Flash request with Google Search for {player_name}"
            )

            # Create content parts
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt_text)],
                ),
            ]

            # Enable Google Search grounding tool
            tools = [
                types.Tool(googleSearch=types.GoogleSearch()),
            ]

            # Configure generation with thinking
            generate_content_config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.7,
                max_output_tokens=2048,
            )

            # Generate response with search grounding
            response = client.models.generate_content(
                model=GeminiSynthesis.MODEL_NAME,
                contents=contents,
                config=generate_content_config,
            )

            # Extract text from response
            response_text = response.text.strip()

            logger.info(f"Raw Gemini response: {response_text[:500]}...")

            # Try to extract JSON from the response
            result = GeminiSynthesis._extract_json(response_text)

            # Ensure required fields exist with defaults
            result.setdefault("recommendation", "FLEX")
            result.setdefault("conviction", "MEDIUM")
            result.setdefault("reasoning", "Analysis based on available data.")
            result.setdefault("key_factors", [])
            result.setdefault("risk_level", "MODERATE")
            result.setdefault("expert_consensus", "Mixed opinions from experts.")
            result.setdefault("sources_used", ["Google Search", "Sleeper API"])

            logger.info(
                f"Gemini synthesis complete for {player_name}: {result.get('recommendation')}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(
                f"Response text: {response_text if 'response_text' in locals() else 'N/A'}"
            )

            return {
                "recommendation": "FLEX",
                "conviction": "LOW",
                "reasoning": "Unable to generate analysis due to parsing error.",
                "key_factors": ["Analysis unavailable"],
                "risk_level": "MODERATE",
                "expert_consensus": "No consensus available",
                "sources_used": ["Sleeper API"],
            }

        except Exception as e:
            logger.error(f"Error in Gemini synthesis for {player_name}: {e}")

            return {
                "recommendation": "FLEX",
                "conviction": "LOW",
                "reasoning": f"Error generating analysis: {str(e)}",
                "key_factors": ["Analysis error"],
                "risk_level": "HIGH",
                "expert_consensus": "Unable to fetch expert opinions",
                "sources_used": ["Sleeper API"],
            }


def get_gemini_service() -> GeminiSynthesis:
    """Get Gemini synthesis service instance."""
    return GeminiSynthesis()
