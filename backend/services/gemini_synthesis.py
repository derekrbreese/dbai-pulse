"""
Gemini 3 Flash synthesis service for dbAI Pulse.
Uses Google's genai SDK with Google Search grounding for real-time fantasy insights.
"""

import asyncio
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

    SYSTEM_INSTRUCTION = (
        "You are a fantasy football analysis assistant for dbAI Pulse. "
        "You MUST only provide information verifiable from search results or the provided data. "
        "Do NOT fabricate statistics, injury reports, trade rumors, or expert quotes. "
        "If you cannot verify something, say so rather than guessing. "
        "Respond ONLY with valid JSON matching the requested schema."
    )
    VALID_RECOMMENDATIONS_REGULAR = {"START", "SIT", "FLEX"}
    VALID_RECOMMENDATIONS_OFFSEASON = {"BUY", "HOLD", "SELL"}
    VALID_CONVICTIONS = {"HIGH", "MEDIUM-HIGH", "MIXED", "MEDIUM-LOW", "LOW"}
    VALID_RISK_LEVELS = {"LOW", "MODERATE", "HIGH"}

    @staticmethod
    def _sanitize_json_text(text: str) -> str:
        """
        Normalize common JSON issues from model output.
        - Replace raw newlines inside strings with \n
        - Strip non-printable control characters
        """
        cleaned = []
        in_string = False
        escape = False

        for ch in text:
            if in_string:
                if escape:
                    cleaned.append(ch)
                    escape = False
                    continue
                if ch == "\\":
                    cleaned.append(ch)
                    escape = True
                    continue
                if ch in ("\n", "\r"):
                    cleaned.append("\\n")
                    continue
            if ch == '"' and not escape:
                in_string = not in_string
            if ord(ch) < 32 and ch not in ("\n", "\r", "\t"):
                continue
            cleaned.append(ch)

        return "".join(cleaned)

    @staticmethod
    def _extract_json(text: str) -> Dict:
        """
        Robustly extract JSON from Gemini response text.
        Handles markdown blocks, extra text, truncated responses, and malformed JSON.
        """
        # First, try to find JSON in markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            candidate = json_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                sanitized = GeminiSynthesis._sanitize_json_text(candidate)
                try:
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    fixed = GeminiSynthesis._fix_truncated_json(sanitized)
                    if fixed:
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            pass

        # Try to find JSON object by looking for { ... }
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            candidate = json_match.group(0)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                sanitized = GeminiSynthesis._sanitize_json_text(candidate)
                try:
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    # Try to fix truncated JSON
                    fixed = GeminiSynthesis._fix_truncated_json(sanitized)
                    if fixed:
                        try:
                            return json.loads(fixed)
                        except json.JSONDecodeError:
                            pass
                # Try to fix truncated JSON

        # If all else fails, try parsing the whole thing
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            sanitized = GeminiSynthesis._sanitize_json_text(text)
            try:
                return json.loads(sanitized)
            except json.JSONDecodeError:
                fixed = GeminiSynthesis._fix_truncated_json(sanitized)
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass
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
    def _is_offseason(season_type: Optional[str]) -> bool:
        """Return True when the NFL is not in an active season (regular or playoffs)."""
        return season_type in (None, 'off', '', 'pre')

    @staticmethod
    def _sanitize_external_text(text: str) -> str:
        """Strip prompt-injection patterns and control characters from external text."""
        injection_patterns = re.compile(
            r"(ignore\s+(all\s+)?previous\s+instructions"
            r"|you\s+are\s+now"
            r"|system\s*:"
            r"|override\s+instructions"
            r"|forget\s+(all\s+)?previous"
            r"|new\s+instructions\s*:?"
            r"|act\s+as\s+if"
            r"|pretend\s+you\s+are"
            r"|respond\s+only\s+with"
            r"|output\s+format\s*:?"
            r"|disregard\s+(prior|previous))",
            re.IGNORECASE,
        )
        sanitized = injection_patterns.sub("[FILTERED]", text)
        # Strip control characters except normal whitespace
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
        return sanitized

    @staticmethod
    def create_synthesis_prompt(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        youtube_context: str = "",
        youtube_sources: Optional[List[str]] = None,
        season: Optional[int] = None,
        week: Optional[int] = None,
        season_type: Optional[str] = None,
        adjusted_projection: Optional[float] = None,
        team: Optional[str] = None,
        bye_week: Optional[int] = None,
    ) -> str:
        """
        Create a synthesis prompt for Gemini with Google Search grounding.
        """
        offseason = GeminiSynthesis._is_offseason(season_type)

        # Dynamic header
        if offseason:
            context_header = f"You are an expert fantasy football analyst. It is currently the {season or 2025} NFL offseason."
        else:
            context_header = f"You are an expert fantasy football analyst helping with Week {week or '?'} of the {season or 2025} NFL season."

        # Build performance summary
        perf_summary = "No recent data available"
        if recent_performance:
            perf_summary = f"""
- L{recent_performance.weeks_analyzed}W Average: {recent_performance.avg_points} pts
- Trend: {recent_performance.trend}
- Weekly Points: {", ".join([str(p) for p in recent_performance.weekly_points])}
"""

        flags_str = ", ".join(flags) if flags else "None"

        youtube_block = ""
        if youtube_context and youtube_context.strip():
            safe_context = GeminiSynthesis._sanitize_external_text(youtube_context)
            youtube_block = f"""
<EXTERNAL_TRANSCRIPT_DATA>
{safe_context}
</EXTERNAL_TRANSCRIPT_DATA>
"""

        source_summaries_instruction = ""
        if youtube_sources:
            source_list = ", ".join(f'"{s}"' for s in youtube_sources)
            source_summaries_instruction = f"""    "expert_source_summaries": {{
        "<source name>": "1-sentence summary of what this source said about the player"
    }},
    The following YouTube sources were analyzed: {source_list}. For each source that had relevant commentary, include a 1-sentence summary in expert_source_summaries. Omit sources with nothing relevant.
"""

        # Offseason vs regular-season task and schema
        if offseason:
            task_block = f"""YOUR TASK:
1. Use Google Search to find the LATEST news, trade rumors, and expert opinions about {player_name}
2. Look for recent Reddit discussions, Twitter/X posts, and fantasy analyst takes
3. Check for any breaking news that affects their dynasty/keeper value
4. Focus on dynasty value, keeper decisions, and upcoming drafts rather than weekly matchups
5. If YouTube expert transcript excerpts are provided above, incorporate their insights into your analysis"""
            rec_schema = '"recommendation": "BUY" | "HOLD" | "SELL",'
            week_note = "- Focus on long-term value, not a specific week's matchup"
        else:
            task_block = f"""YOUR TASK:
1. Use Google Search to find the LATEST news, injury updates, and expert opinions about {player_name} for this week
2. Look for recent Reddit discussions, Twitter/X posts, and fantasy analyst takes
3. Check for any breaking news that affects their value
4. Consider their matchup this week
5. If YouTube expert transcript excerpts are provided above, incorporate their insights into your analysis"""
            rec_schema = '"recommendation": "START" | "SIT" | "FLEX",'
            week_note = "- Be specific about THIS WEEK's outlook"

        # Build extra stat lines
        extra_stats = ""
        if team:
            extra_stats += f"- Team: {team}\n"
        if adjusted_projection and adjusted_projection != projection:
            extra_stats += f"- Adjusted Projection: {adjusted_projection} pts\n"
        if bye_week:
            extra_stats += f"- Bye Week: {bye_week}\n"

        prompt = f"""{context_header}

PLAYER: {player_name} ({position})

STATISTICAL DATA FROM SLEEPER API:
- Projected Points: {projection} pts
{extra_stats}{perf_summary}
- Performance Flags: {flags_str}
{youtube_block}
{task_block}

Based on ALL available information (stats + live search results + expert transcripts), provide a JSON response:
{{
    {rec_schema}
    "conviction": "HIGH" | "MEDIUM-HIGH" | "MIXED" | "MEDIUM-LOW" | "LOW",
    "reasoning": "2-3 sentence explanation citing specific sources you found",
    "key_factors": ["factor 1 with source", "factor 2 with source", "factor 3 with source"],
    "risk_level": "LOW" | "MODERATE" | "HIGH",
    "expert_consensus": "summary of what fantasy experts are saying, cite sources",
    "sources_used": ["source 1", "source 2", "source 3"],
{source_summaries_instruction}}}

IMPORTANT:
- Cite specific sources you find (e.g., "FantasyPros ranks him...", "Reddit r/fantasyfootball says...")
- Include any injury news or matchup concerns
{week_note}
- For expert_source_summaries, write clean summaries (NOT raw transcript quotes)

Respond ONLY with valid JSON, no markdown formatting."""

        return prompt

    @staticmethod
    async def synthesize_player_analysis(
        player_name: str,
        position: str,
        projection: float,
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        youtube_context: str = "",
        youtube_sources: Optional[List[str]] = None,
        season: Optional[int] = None,
        week: Optional[int] = None,
        season_type: Optional[str] = None,
        adjusted_projection: Optional[float] = None,
        team: Optional[str] = None,
        bye_week: Optional[int] = None,
        on_bye: bool = False,
    ) -> Dict:
        """
        Use Gemini 3 Flash with Google Search grounding to synthesize insights.
        """
        offseason = GeminiSynthesis._is_offseason(season_type)
        fallback_rec = "HOLD" if offseason else "FLEX"

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
                youtube_sources=youtube_sources,
                season=season,
                week=week,
                season_type=season_type,
                adjusted_projection=adjusted_projection,
                team=team,
                bye_week=bye_week,
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

            # Configure generation
            generate_content_config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.3,
                max_output_tokens=4096,
                system_instruction=GeminiSynthesis.SYSTEM_INSTRUCTION,
            )

            # Generate response with search grounding (with timeout)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=GeminiSynthesis.MODEL_NAME,
                    contents=contents,
                    config=generate_content_config,
                ),
                timeout=30,
            )

            # Extract text from response
            response_text = response.text.strip()

            logger.info(f"Raw Gemini response: {response_text[:500]}...")

            # Try to extract JSON from the response
            result = GeminiSynthesis._extract_json(response_text)

            # Validate and default enum fields
            valid_recs = (
                GeminiSynthesis.VALID_RECOMMENDATIONS_OFFSEASON
                if offseason
                else GeminiSynthesis.VALID_RECOMMENDATIONS_REGULAR
            )
            if result.get("recommendation") not in valid_recs:
                logger.warning(
                    f"Invalid recommendation '{result.get('recommendation')}' for {player_name}, defaulting to {fallback_rec}"
                )
                result["recommendation"] = fallback_rec
            if result.get("conviction") not in GeminiSynthesis.VALID_CONVICTIONS:
                logger.warning(
                    f"Invalid conviction '{result.get('conviction')}' for {player_name}, defaulting to MIXED"
                )
                result["conviction"] = "MIXED"
            if result.get("risk_level") not in GeminiSynthesis.VALID_RISK_LEVELS:
                logger.warning(
                    f"Invalid risk_level '{result.get('risk_level')}' for {player_name}, defaulting to MODERATE"
                )
                result["risk_level"] = "MODERATE"

            # Ensure required fields exist with defaults
            result.setdefault("recommendation", fallback_rec)
            result.setdefault("conviction", "MIXED")
            result.setdefault("reasoning", "Analysis based on available data.")
            result.setdefault("key_factors", [])
            result.setdefault("risk_level", "MODERATE")
            result.setdefault("expert_consensus", "Mixed opinions from experts.")
            result.setdefault("sources_used", ["Google Search", "Sleeper API"])

            # Fix 2: Cap conviction when data is sparse
            has_youtube = bool(youtube_context and youtube_context.strip())
            weeks_analyzed = recent_performance.weeks_analyzed if recent_performance else 0
            if not has_youtube and weeks_analyzed < 3:
                current_conviction = result.get("conviction", "MIXED")
                if current_conviction in ("HIGH", "MEDIUM-HIGH"):
                    logger.warning(
                        f"Downgrading conviction for {player_name} from {current_conviction} to MIXED "
                        f"(no YouTube context, only {weeks_analyzed} weeks analyzed)"
                    )
                    result["conviction"] = "MIXED"

            # Fix 4: Bye week hard-override
            if on_bye:
                result["recommendation"] = "SIT"
                result["reasoning"] = "Player is on bye this week. " + result.get("reasoning", "")
                result["risk_level"] = "LOW"
                result["conviction"] = "HIGH"
                logger.info(f"Bye week override applied for {player_name}")

            logger.info(
                f"Gemini synthesis complete for {player_name}: {result.get('recommendation')}"
            )

            return result

        except TimeoutError:
            logger.error(f"Gemini synthesis timed out for {player_name}")
            return {
                "recommendation": fallback_rec,
                "conviction": "LOW",
                "reasoning": "Analysis temporarily unavailable due to timeout.",
                "key_factors": ["Analysis unavailable"],
                "risk_level": "MODERATE",
                "expert_consensus": "No consensus available",
                "sources_used": ["Sleeper API"],
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(
                f"Response text: {response_text if 'response_text' in locals() else 'N/A'}"
            )

            return {
                "recommendation": fallback_rec,
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
                "recommendation": fallback_rec,
                "conviction": "LOW",
                "reasoning": "Analysis temporarily unavailable. Please try again shortly.",
                "key_factors": ["Analysis unavailable"],
                "risk_level": "MODERATE",
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
        season: Optional[int] = None,
        week: Optional[int] = None,
        season_type: Optional[str] = None,
    ) -> Dict:
        """
        Compare two players using Gemini with Google Search grounding.
        """
        offseason = GeminiSynthesis._is_offseason(season_type)

        try:
            client = genai.Client(api_key=settings.gemini_api_key)

            flags_a = ", ".join(player_a_flags) if player_a_flags else "None"
            flags_b = ", ".join(player_b_flags) if player_b_flags else "None"

            if offseason:
                context_line = f"You are an expert fantasy football analyst. It is currently the {season or 2025} NFL offseason. Compare these two players for dynasty/keeper value."
                search_block = """Use Google Search to find:
1. Offseason news, trades, and coaching changes for both players
2. Injury recovery updates or concerns
3. Expert dynasty rankings and analyst opinions
4. Recent news affecting their long-term value"""
                edge_field = '"value_edge": "Who has more long-term value and why"'
            else:
                context_line = f"You are an expert fantasy football analyst. Compare these two players for Week {week or '?'} of the {season or 2025} NFL season."
                search_block = """Use Google Search to find:
1. Current matchup info for both players
2. Injury news or concerns
3. Expert rankings and analyst opinions
4. Recent news affecting their value"""
                edge_field = '"matchup_edge": "Who has the better matchup and why"'

            prompt = f"""{context_line}

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

{search_block}

Based on all available info, return JSON:
{{
    "winner": "A" | "B" | "TOSS_UP",
    "conviction": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "2-3 sentences explaining your pick, citing sources",
    "key_advantages_a": ["advantage 1", "advantage 2"],
    "key_advantages_b": ["advantage 1", "advantage 2"],
    {edge_field},
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
                temperature=0.3,
                max_output_tokens=4096,
                system_instruction=GeminiSynthesis.SYSTEM_INSTRUCTION,
            )

            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=GeminiSynthesis.MODEL_NAME,
                    contents=contents,
                    config=config,
                ),
                timeout=30,
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

            # Set defaults — normalize value_edge → matchup_edge for offseason
            result.setdefault("winner", "TOSS_UP")
            result.setdefault("conviction", "MEDIUM")
            result.setdefault("reasoning", "Both players have similar value.")
            result.setdefault("key_advantages_a", [])
            result.setdefault("key_advantages_b", [])
            if "value_edge" in result and "matchup_edge" not in result:
                result["matchup_edge"] = result.pop("value_edge")
            result.setdefault("matchup_edge", "Similar matchups" if not offseason else "Similar long-term value")
            result.setdefault("sources_used", ["Google Search", "Sleeper API"])

            return result

        except TimeoutError:
            logger.error("Gemini comparison timed out")
            return {
                "winner": "TOSS_UP",
                "conviction": "LOW",
                "reasoning": "Comparison temporarily unavailable due to timeout.",
                "key_advantages_a": [],
                "key_advantages_b": [],
                "matchup_edge": "Unable to determine",
                "sources_used": ["Sleeper API"],
            }

        except Exception as e:
            logger.error(f"Error comparing players: {e}")
            return {
                "winner": "TOSS_UP",
                "conviction": "LOW",
                "reasoning": "Comparison temporarily unavailable. Please try again shortly.",
                "key_advantages_a": [],
                "key_advantages_b": [],
                "matchup_edge": "Unable to determine",
                "sources_used": ["Sleeper API"],
            }


def get_gemini_service() -> GeminiSynthesis:
    """Get Gemini synthesis service instance."""
    return GeminiSynthesis()
