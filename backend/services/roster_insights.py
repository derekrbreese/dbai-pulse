"""
Roster insights service for imported Yahoo teams.
"""

import difflib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from config import get_settings
from models.schemas import (
    EnhancedPlayer,
    PlayerBase,
    PlayerProjection,
    RecentPerformance,
    RosterInsightPlayer,
    RosterInsightsResponse,
    TeamFeedbackPreferences,
    YahooTeamSummary,
)
from services.enhancement import get_enhancement_engine
from services.sleeper import get_sleeper_client

logger = logging.getLogger(__name__)

_suffix_pattern = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)
_non_alpha_pattern = re.compile(r"[^a-z0-9 ]")
_multi_space_pattern = re.compile(r"\s+")

_sleeper_player_index: Optional[Dict[str, Any]] = None


class RosterInsightsService:
    """Builds enhanced insights for Yahoo roster players."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sleeper = get_sleeper_client()
        self.engine = get_enhancement_engine()

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize names for resilient Yahoo-to-Sleeper matching."""
        lowered = (name or "").lower().replace("'", "")
        lowered = _suffix_pattern.sub("", lowered)
        lowered = _non_alpha_pattern.sub(" ", lowered)
        lowered = _multi_space_pattern.sub(" ", lowered).strip()
        return lowered

    @staticmethod
    def normalize_team(team: Optional[str]) -> str:
        """Normalize NFL team abbreviations used by matching index."""
        return (team or "").strip().upper()

    @staticmethod
    def normalize_position(position: Optional[str]) -> str:
        """Normalize Yahoo roster position labels into Sleeper-style labels."""
        raw = (position or "").strip().upper()
        if raw in {"QB", "RB", "WR", "TE", "K", "DEF"}:
            return raw
        if raw in {"D/ST", "DST"}:
            return "DEF"

        # Combined slots and flex positions are not position-precise.
        if "/" in raw or raw in {"W/R/T", "W/R", "BN", "IR", "FLEX", "UTIL"}:
            return ""
        return raw

    async def _build_player_index(self) -> Dict[str, Any]:
        """Build and cache Sleeper player lookup indexes."""
        global _sleeper_player_index
        if _sleeper_player_index is not None:
            return _sleeper_player_index

        players = await self.sleeper.get_all_players()
        name_team: Dict[Tuple[str, str], List[str]] = {}
        name_pos: Dict[Tuple[str, str], List[str]] = {}
        name_only: Dict[str, List[str]] = {}
        meta: Dict[str, Dict[str, Any]] = {}

        valid_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}

        for sleeper_id, player in players.items():
            position = (player.get("position") or "").upper()
            if position not in valid_positions:
                continue

            first_name = player.get("first_name") or ""
            last_name = player.get("last_name") or ""
            full_name = f"{first_name} {last_name}".strip()
            normalized = self.normalize_name(full_name)
            if not normalized:
                continue

            team = self.normalize_team(player.get("team"))

            meta[sleeper_id] = {
                "name": full_name,
                "team": team,
                "position": position,
                "search_rank": player.get("search_rank") or 999999,
            }

            name_only.setdefault(normalized, []).append(sleeper_id)
            if team:
                name_team.setdefault((normalized, team), []).append(sleeper_id)
            name_pos.setdefault((normalized, position), []).append(sleeper_id)

        _sleeper_player_index = {
            "name_team": name_team,
            "name_pos": name_pos,
            "name_only": name_only,
            "meta": meta,
            "names": list(name_only.keys()),
        }
        return _sleeper_player_index

    @staticmethod
    def _pick_candidate(
        candidates: List[str],
        meta: Dict[str, Dict[str, Any]],
        preferred_team: str,
        preferred_position: str,
    ) -> Optional[str]:
        """Choose best candidate from a list using team/position/search_rank heuristics."""
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        if preferred_team:
            team_candidates = [sid for sid in candidates if meta.get(sid, {}).get("team") == preferred_team]
            if len(team_candidates) == 1:
                return team_candidates[0]
            if team_candidates:
                candidates = team_candidates

        if preferred_position:
            pos_candidates = [
                sid for sid in candidates if meta.get(sid, {}).get("position") == preferred_position
            ]
            if len(pos_candidates) == 1:
                return pos_candidates[0]
            if pos_candidates:
                candidates = pos_candidates

        return sorted(candidates, key=lambda sid: meta.get(sid, {}).get("search_rank", 999999))[0]

    async def match_player(self, yahoo_player: Dict[str, Any]) -> Tuple[Optional[str], Optional[float], str]:
        """Match a Yahoo roster player to a Sleeper player ID."""
        index = await self._build_player_index()

        name = self.normalize_name(yahoo_player.get("name", ""))
        if not name:
            return None, None, "missing player name"

        team = self.normalize_team(yahoo_player.get("team"))
        position = self.normalize_position(yahoo_player.get("position"))

        name_team = index["name_team"]
        name_pos = index["name_pos"]
        name_only = index["name_only"]
        meta = index["meta"]

        exact_team_candidates = name_team.get((name, team), []) if team else []
        candidate = self._pick_candidate(exact_team_candidates, meta, team, position)
        if candidate:
            return candidate, 1.0, "exact name+team match"

        exact_position_candidates = name_pos.get((name, position), []) if position else []
        candidate = self._pick_candidate(exact_position_candidates, meta, team, position)
        if candidate:
            return candidate, 0.97, "exact name+position match"

        strict_name_candidates = name_only.get(name, [])
        candidate = self._pick_candidate(strict_name_candidates, meta, team, position)
        if candidate:
            confidence = 0.95 if len(strict_name_candidates) == 1 else 0.9
            reason = "strict name unique match" if len(strict_name_candidates) == 1 else "strict name best-match"
            return candidate, confidence, reason

        fuzzy_matches = difflib.get_close_matches(name, index["names"], n=1, cutoff=0.92)
        if fuzzy_matches:
            fuzzy_name = fuzzy_matches[0]
            fuzzy_candidates = name_only.get(fuzzy_name, [])
            candidate = self._pick_candidate(fuzzy_candidates, meta, team, position)
            if candidate:
                return candidate, 0.92, f"fuzzy name match ({fuzzy_name})"

        return None, None, "no high-confidence sleeper match"

    @staticmethod
    def _build_context_message(
        on_bye: bool,
        bye_week: Optional[int],
        recent_performance: Optional[RecentPerformance],
        flags: List[str],
        projection_source: str,
        adjusted_projection: Optional[float],
        projection_value: float,
    ) -> str:
        """Create short context message for enhanced player cards."""
        if on_bye:
            return f"Player is on bye (Week {bye_week})"

        if projection_source == "recent_avg" and recent_performance:
            return (
                f"Using L{recent_performance.weeks_analyzed}W avg "
                f"({recent_performance.avg_points} pts)"
            )
        if projection_source == "recent_projection":
            return "Using recent projection avg"
        if projection_source == "recent_baseline":
            return "Using prior-week avg baseline"

        if flags:
            headline = flags[0].replace("_", " ")
            if adjusted_projection is not None and adjusted_projection != projection_value:
                delta = adjusted_projection - projection_value
                sign = "+" if delta > 0 else ""
                return f"{headline} ({sign}{delta:.1f} pts adj)"
            return headline

        if recent_performance:
            return f"L{recent_performance.weeks_analyzed}W avg: {recent_performance.avg_points} pts"

        return "No recent performance data"

    async def build_enhanced_player(self, sleeper_id: str, scoring: str) -> Optional[EnhancedPlayer]:
        """Build `EnhancedPlayer` payload for a matched Sleeper player id."""
        player_data = await self.sleeper.get_player(sleeper_id)
        if not player_data:
            return None

        player = PlayerBase(**player_data)
        current_season, current_week = await self.sleeper.get_current_season_week(
            self.settings.nfl_season, self.settings.nfl_week
        )

        on_bye = player.bye_week == current_week
        projection_value = 0.0
        projection_source = "sleeper"
        if not on_bye:
            projection_value = await self.sleeper.get_player_projection(
                sleeper_id, current_season, current_week, scoring=scoring
            )

        recent_data = await self.sleeper.get_recent_performance(
            sleeper_id,
            current_season,
            current_week,
            lookback=3,
            scoring=scoring,
        )
        recent_performance = None
        if recent_data.get("weeks_analyzed", 0) > 0:
            recent_performance = RecentPerformance(**recent_data)

        previous_avg = 0.0
        if recent_performance and len(recent_performance.weekly_points) > 1:
            previous_avg = sum(recent_performance.weekly_points[1:]) / (
                len(recent_performance.weekly_points) - 1
            )

        if projection_value == 0 and recent_performance:
            projection_value = await self.sleeper.get_recent_projection_avg(
                sleeper_id, current_season, current_week, lookback=3, scoring=scoring
            )
            if projection_value > 0:
                projection_source = "recent_projection"
        if projection_value == 0 and previous_avg > 0:
            projection_value = round(previous_avg, 1)
            projection_source = "recent_baseline"
        if projection_value == 0 and recent_performance:
            projection_value = recent_performance.avg_points
            projection_source = "recent_avg"

        flags: List[str] = []
        adjusted_value: Optional[float] = None
        if recent_performance and not on_bye and projection_value > 0:
            flags = self.engine.calculate_flags(projection_value, recent_performance)
            if flags:
                adjusted_value = self.engine.calculate_adjusted_projection(
                    projection_value, recent_performance, flags
                )

        projection = PlayerProjection(
            sleeper_projection=projection_value,
            adjusted_projection=adjusted_value,
        )
        context = self._build_context_message(
            on_bye=on_bye,
            bye_week=player.bye_week,
            recent_performance=recent_performance,
            flags=flags,
            projection_source=projection_source,
            adjusted_projection=adjusted_value,
            projection_value=projection_value,
        )

        return EnhancedPlayer(
            player=player,
            projection=projection,
            recent_performance=recent_performance,
            performance_flags=flags,
            context_message=context,
            on_bye=on_bye,
            draft_value=None,
        )

    @staticmethod
    def _calculate_feedback_score(
        enhanced_player: Optional[EnhancedPlayer],
        risk: str,
        focus: str,
        status: Optional[str],
        injury_status: Optional[str],
    ) -> Optional[float]:
        """Calculate customization-aware feedback score."""
        if not enhanced_player:
            return None

        projection = (
            enhanced_player.projection.adjusted_projection
            if enhanced_player.projection.adjusted_projection is not None
            else enhanced_player.projection.sleeper_projection
        )
        flags = set(enhanced_player.performance_flags)
        recent = enhanced_player.recent_performance

        score = float(projection)
        if recent:
            score += (recent.avg_points - projection) * 0.5

        if "BREAKOUT_CANDIDATE" in flags:
            score += 2.0
        if "TRENDING_UP" in flags:
            score += 1.2
        if "HIGH_CEILING" in flags:
            score += 1.4
        if "CONSISTENT" in flags:
            score += 0.8
        if "UNDERPERFORMING" in flags:
            score -= 1.0
        if "DECLINING_ROLE" in flags:
            score -= 2.0
        if "BOOM_BUST" in flags:
            score -= 0.5

        if risk == "conservative":
            if "BOOM_BUST" in flags:
                score -= 1.5
            if "CONSISTENT" in flags:
                score += 1.0
            if injury_status:
                score -= 1.5
        elif risk == "aggressive":
            if "BREAKOUT_CANDIDATE" in flags:
                score += 1.2
            if "HIGH_CEILING" in flags:
                score += 1.2
            if "CONSISTENT" in flags:
                score -= 0.4

        if focus == "floor":
            if "CONSISTENT" in flags:
                score += 1.5
            if "BOOM_BUST" in flags:
                score -= 1.5
        elif focus == "upside":
            if "TRENDING_UP" in flags:
                score += 1.2
            if "BREAKOUT_CANDIDATE" in flags:
                score += 1.0
        elif focus == "ceiling":
            if "HIGH_CEILING" in flags:
                score += 2.0
            if recent and recent.weekly_points:
                score += max(recent.weekly_points) * 0.05

        if status and status.strip().upper() in {"OUT", "DOUBTFUL", "SUSP"}:
            score -= 3.0
        if injury_status:
            score -= 0.8

        return round(max(score, 0.0), 1)

    @staticmethod
    def _build_custom_feedback(
        enhanced_player: Optional[EnhancedPlayer],
        risk: str,
        focus: str,
        match_reason: str,
        feedback_score: Optional[float],
    ) -> str:
        """Build short user-facing feedback sentence."""
        if not enhanced_player:
            return (
                f"Unable to score automatically ({match_reason}). "
                "This player did not confidently map to Sleeper."
            )

        flags = enhanced_player.performance_flags
        if not flags:
            return (
                f"Stable baseline profile ({risk}/{focus}) with projected "
                f"{enhanced_player.projection.sleeper_projection:.1f} pts."
            )

        top_flag = flags[0].replace("_", " ").title()
        score_text = f"feedback {feedback_score:.1f}" if feedback_score is not None else "feedback unavailable"
        return f"{top_flag} signal under {risk}/{focus} profile ({score_text})."

    @staticmethod
    def _parse_ids_from_keys(team_key: str, league_key: str) -> Tuple[str, str]:
        """Extract numeric league/team IDs from Yahoo keys."""
        try:
            league_id = league_key.split(".")[-1]
            team_id = team_key.split(".")[-1]
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid Yahoo team_key/league_key format.") from exc

        if not league_id or not team_id:
            raise HTTPException(status_code=400, detail="Invalid Yahoo team_key/league_key format.")
        return league_id, team_id

    async def generate_team_insights(
        self,
        yahoo_service: Any,
        team_summary: Dict[str, Any],
        preferences: TeamFeedbackPreferences,
    ) -> RosterInsightsResponse:
        """Build full roster insights payload for one Yahoo team."""
        team_key = team_summary.get("team_key")
        league_key = team_summary.get("league_key")
        if not team_key or not league_key:
            raise HTTPException(status_code=400, detail="team_key and league_key are required for insights.")

        league_id, team_id = self._parse_ids_from_keys(team_key, league_key)
        roster = await yahoo_service.get_team_roster(league_id, team_id, team_key=team_key)

        players: List[RosterInsightPlayer] = []
        matched_count = 0
        unmatched_count = 0

        for yahoo_player in roster:
            sleeper_id, confidence, match_reason = await self.match_player(yahoo_player)
            enhanced_player = None
            if sleeper_id:
                enhanced_player = await self.build_enhanced_player(sleeper_id, preferences.scoring)

            score = self._calculate_feedback_score(
                enhanced_player=enhanced_player,
                risk=preferences.risk,
                focus=preferences.focus,
                status=yahoo_player.get("status"),
                injury_status=yahoo_player.get("injury_status"),
            )
            feedback = self._build_custom_feedback(
                enhanced_player=enhanced_player,
                risk=preferences.risk,
                focus=preferences.focus,
                match_reason=match_reason,
                feedback_score=score,
            )

            if enhanced_player:
                matched_count += 1
            else:
                unmatched_count += 1

            players.append(
                RosterInsightPlayer(
                    yahoo_player_key=yahoo_player.get("player_key") or yahoo_player.get("player_id") or "",
                    name=yahoo_player.get("name", "Unknown"),
                    position=yahoo_player.get("position"),
                    team=yahoo_player.get("team"),
                    status=yahoo_player.get("status"),
                    injury_status=yahoo_player.get("injury_status"),
                    matched_sleeper_id=sleeper_id,
                    match_confidence=confidence,
                    match_reason=match_reason,
                    enhanced_player=enhanced_player,
                    custom_feedback=feedback,
                    feedback_score=score,
                )
            )

        imported_at = int(time.time())
        summary = (
            f"Matched {matched_count} of {len(players)} players. "
            f"{unmatched_count} players require manual review."
        )

        return RosterInsightsResponse(
            team=YahooTeamSummary(
                team_key=team_key,
                team_name=team_summary.get("team_name") or team_summary.get("name") or "Unknown Team",
                league_key=league_key,
                league_name=team_summary.get("league_name"),
                season=team_summary.get("season"),
            ),
            preferences=preferences,
            players=players,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            summary=summary,
            cached=False,
            imported_at=imported_at,
        )


_roster_insights_service: Optional[RosterInsightsService] = None


def get_roster_insights_service() -> RosterInsightsService:
    """Get or create roster insights service singleton."""
    global _roster_insights_service
    if _roster_insights_service is None:
        _roster_insights_service = RosterInsightsService()
    return _roster_insights_service
