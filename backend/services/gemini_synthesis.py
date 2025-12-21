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
        Handles markdown blocks, extra text, truncated responses, and malformed JSON.
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
                # Try to fix truncated JSON
                json_text = json_match.group(0)
                fixed = GeminiSynthesis._fix_truncated_json(json_text)
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass

        # If all else fails, try parsing the whole thing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Could not extract JSON from response: {text[:200]}...")
            raise

    @staticmethod
    def _fix_truncated_json(text: str) -> Optional[str]:
        """
        Attempt to fix truncated JSON by closing open strings, arrays, and objects.
        """
        # Count unbalanced brackets
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        # Check if we're in the middle of a string (odd number of unescaped quotes)
        in_string = False
        i = 0
        while i < len(text):
            if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                in_string = not in_string
            i += 1

        fixed = text

        # Close open string
        if in_string:
            fixed += '"'

        # Close arrays and objects
        fixed += ']' * open_brackets
        fixed += '}' * open_braces

        return fixed if fixed != text else None

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

            # Configure generation - increased token limit for complete JSON responses
            generate_content_config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.7,
                max_output_tokens=4096,
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

    @staticmethod
    async def compare_players(
        player_a_name: str,
        player_a_position: str,
        player_a_projection: float,
        player_a_avg: float,
        player_a_trend: str,
        player_a_flags: List[str],
        player_b_name: str,
        player_b_position: str,
        player_b_projection: float,
        player_b_avg: float,
        player_b_trend: str,
        player_b_flags: List[str],
    ) -> Dict:
        """
        Compare two players using Gemini with Google Search grounding.
        """
        try:
            client = genai.Client(api_key=settings.gemini_api_key)

            flags_a = ", ".join(player_a_flags) if player_a_flags else "None"
            flags_b = ", ".join(player_b_flags) if player_b_flags else "None"

            prompt = f"""You are an expert fantasy football analyst. Compare these two players for Week 16 of the 2025 NFL season.

PLAYER A: {player_a_name} ({player_a_position})
- Projection: {player_a_projection} pts
- L3W Average: {player_a_avg} pts
- Trend: {player_a_trend}
- Flags: {flags_a}

PLAYER B: {player_b_name} ({player_b_position})
- Projection: {player_b_projection} pts
- L3W Average: {player_b_avg} pts
- Trend: {player_b_trend}
- Flags: {flags_b}

Use Google Search to find:
1. Current matchup info for both players
2. Injury news or concerns
3. Expert rankings and analyst opinions
4. Recent news affecting their value

Based on all available info, return JSON:
{{
    "winner": "A" | "B" | "TOSS_UP",
    "conviction": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "2-3 sentences explaining your pick, citing sources",
    "key_advantages_a": ["advantage 1", "advantage 2"],
    "key_advantages_b": ["advantage 1", "advantage 2"],
    "matchup_edge": "Who has the better matchup and why",
    "sources_used": ["source 1", "source 2"]
}}

Respond ONLY with valid JSON."""

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ]

            tools = [types.Tool(googleSearch=types.GoogleSearch())]

            config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.7,
                max_output_tokens=4096,
            )

            response = client.models.generate_content(
                model=GeminiSynthesis.MODEL_NAME,
                contents=contents,
                config=config,
            )

            # Handle potentially empty response
            response_text = ""
            if response and response.text:
                response_text = response.text.strip()

            logger.info(f"Comparison response length: {len(response_text)}")
            if response_text:
                logger.info(f"Comparison response: {response_text[:300]}...")

            if not response_text:
                logger.warning("Gemini returned empty response for comparison")
                raise ValueError("Empty response from Gemini")

            result = GeminiSynthesis._extract_json(response_text)

            # Set defaults
            result.setdefault("winner", "TOSS_UP")
            result.setdefault("conviction", "MEDIUM")
            result.setdefault("reasoning", "Both players have similar value.")
            result.setdefault("key_advantages_a", [])
            result.setdefault("key_advantages_b", [])
            result.setdefault("matchup_edge", "Similar matchups")
            result.setdefault("sources_used", ["Google Search", "Sleeper API"])

            return result

        except Exception as e:
            logger.error(f"Error comparing players: {e}")
            return {
                "winner": "TOSS_UP",
                "conviction": "LOW",
                "reasoning": f"Error during comparison: {str(e)}",
                "key_advantages_a": [],
                "key_advantages_b": [],
                "matchup_edge": "Unable to determine",
                "sources_used": ["Sleeper API"],
            }


def get_gemini_service() -> GeminiSynthesis:
    """Get Gemini synthesis service instance."""
    return GeminiSynthesis()
