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
from services.storage import get_storage

logger = logging.getLogger(__name__)

_suffix_pattern = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.IGNORECASE)
_non_alpha_pattern = re.compile(r"[^a-z0-9 ]")
_multi_space_pattern = re.compile(r"\s+")

_TEAM_ABBREVIATION_ALIASES: Dict[str, str] = {
    "ARZ": "ARI",
    "JAC": "JAX",
    "LA": "LAR",
    "LVR": "LV",
    "NWE": "NE",
    "NOR": "NO",
    "OAK": "LV",
    "SD": "LAC",
    "SFO": "SF",
    "STL": "LAR",
    "TAM": "TB",
    "WSH": "WAS",
}

_sleeper_player_index: Optional[Dict[str, Any]] = None


class RosterInsightsService:
    """Builds enhanced insights for Yahoo roster players."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.sleeper = get_sleeper_client()
        self.engine = get_enhancement_engine()
        self.storage = get_storage()

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize names for resilient Yahoo-to-Sleeper matching."""
        lowered = (name or "").lower().replace("'", "")
        lowered = _suffix_pattern.sub("", lowered)
        lowered = _non_alpha_pattern.sub(" ", lowered)
        lowered = _multi_space_pattern.sub(" ", lowered).strip()
        return lowered

    @staticmethod
    def normalize_name_compact(name: str) -> str:
        """Normalize and collapse spaces for robust initial-based name matching."""
        return RosterInsightsService.normalize_name(name).replace(" ", "")

    @staticmethod
    def normalize_team(team: Optional[str]) -> str:
        """Normalize NFL team abbreviations used by matching index."""
        raw = (team or "").strip().upper()
        if not raw:
            return ""
        return _TEAM_ABBREVIATION_ALIASES.get(raw, raw)

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

    @staticmethod
    def _safe_search_rank(value: Any) -> int:
        """Convert search_rank into sortable int with fallback."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 999999

    async def _build_player_index(self) -> Dict[str, Any]:
        """Build and cache Sleeper player lookup indexes."""
        global _sleeper_player_index
        if _sleeper_player_index is not None:
            return _sleeper_player_index

        players = await self.sleeper.get_all_players()
        name_team: Dict[Tuple[str, str], List[str]] = {}
        name_pos: Dict[Tuple[str, str], List[str]] = {}
        name_only: Dict[str, List[str]] = {}
        name_team_compact: Dict[Tuple[str, str], List[str]] = {}
        name_pos_compact: Dict[Tuple[str, str], List[str]] = {}
        name_only_compact: Dict[str, List[str]] = {}
        yahoo_id: Dict[str, List[str]] = {}
        def_by_team: Dict[str, List[str]] = {}
        meta: Dict[str, Dict[str, Any]] = {}

        valid_positions = {"QB", "RB", "WR", "TE", "K", "DEF"}

        for sleeper_id, player in players.items():
            position = (player.get("position") or "").upper()
            if position not in valid_positions:
                continue

            first_name = player.get("first_name") or ""
            last_name = player.get("last_name") or ""
            full_name = (
                player.get("full_name")
                or f"{first_name} {last_name}"
                or player.get("search_full_name")
                or ""
            ).strip()

            normalized_names: List[str] = []
            for raw_name in {
                full_name,
                f"{first_name} {last_name}".strip(),
                player.get("search_full_name") or "",
            }:
                normalized = self.normalize_name(raw_name)
                if normalized and normalized not in normalized_names:
                    normalized_names.append(normalized)

            if not normalized_names:
                continue

            team = self.normalize_team(player.get("team"))

            meta[sleeper_id] = {
                "name": full_name,
                "team": team,
                "position": position,
                "search_rank": self._safe_search_rank(player.get("search_rank")),
                "has_team": bool(team),
                "normalized_names": normalized_names,
                "compact_names": [self.normalize_name_compact(item) for item in normalized_names],
            }

            for normalized_name in normalized_names:
                if sleeper_id not in name_only.setdefault(normalized_name, []):
                    name_only[normalized_name].append(sleeper_id)
                if team:
                    team_key = (normalized_name, team)
                    if sleeper_id not in name_team.setdefault(team_key, []):
                        name_team[team_key].append(sleeper_id)

                pos_key = (normalized_name, position)
                if sleeper_id not in name_pos.setdefault(pos_key, []):
                    name_pos[pos_key].append(sleeper_id)

                compact_name = self.normalize_name_compact(normalized_name)
                if compact_name:
                    if sleeper_id not in name_only_compact.setdefault(compact_name, []):
                        name_only_compact[compact_name].append(sleeper_id)
                    if team:
                        compact_team_key = (compact_name, team)
                        if sleeper_id not in name_team_compact.setdefault(compact_team_key, []):
                            name_team_compact[compact_team_key].append(sleeper_id)
                    compact_pos_key = (compact_name, position)
                    if sleeper_id not in name_pos_compact.setdefault(compact_pos_key, []):
                        name_pos_compact[compact_pos_key].append(sleeper_id)

            sleeper_yahoo_id = player.get("yahoo_id")
            if sleeper_yahoo_id is not None:
                sleeper_yahoo_id = str(sleeper_yahoo_id).strip()
                if sleeper_yahoo_id:
                    if sleeper_id not in yahoo_id.setdefault(sleeper_yahoo_id, []):
                        yahoo_id[sleeper_yahoo_id].append(sleeper_id)

            if position == "DEF" and team:
                if sleeper_id not in def_by_team.setdefault(team, []):
                    def_by_team[team].append(sleeper_id)

        _sleeper_player_index = {
            "name_team": name_team,
            "name_pos": name_pos,
            "name_only": name_only,
            "name_team_compact": name_team_compact,
            "name_pos_compact": name_pos_compact,
            "name_only_compact": name_only_compact,
            "yahoo_id": yahoo_id,
            "def_by_team": def_by_team,
            "meta": meta,
            "names": list(name_only.keys()),
            "compact_names": list(name_only_compact.keys()),
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

        return sorted(
            candidates,
            key=lambda sid: (
                0 if meta.get(sid, {}).get("has_team") else 1,
                meta.get(sid, {}).get("search_rank", 999999),
            ),
        )[0]

    @staticmethod
    def _extract_yahoo_player_identifiers(yahoo_player: Dict[str, Any]) -> Tuple[str, str]:
        """Extract Yahoo player_key and player_id with fallback parsing from key."""
        player_key = str(yahoo_player.get("player_key") or "").strip()
        player_id = str(yahoo_player.get("player_id") or "").strip()

        if not player_id and player_key and ".p." in player_key:
            player_id = player_key.split(".p.")[-1].strip()

        return player_key, player_id

    def _saved_mapping_is_compatible(
        self,
        sleeper_id: str,
        yahoo_player: Dict[str, Any],
        index: Dict[str, Any],
    ) -> bool:
        """Validate that saved mapping is still compatible with current roster metadata."""
        meta = index.get("meta", {})
        sleeper_meta = meta.get(sleeper_id)
        if not sleeper_meta:
            return False

        yahoo_team = self.normalize_team(yahoo_player.get("team"))
        yahoo_position = self.normalize_position(yahoo_player.get("position"))
        sleeper_position = sleeper_meta.get("position") or ""
        sleeper_team = sleeper_meta.get("team") or ""

        if yahoo_position and sleeper_position and yahoo_position != sleeper_position:
            return False

        # Defenses should be team-locked.
        if yahoo_position == "DEF" and yahoo_team and sleeper_team and yahoo_team != sleeper_team:
            return False

        return True

    def _resolve_saved_mapping(
        self,
        user_id: Optional[str],
        team_key: Optional[str],
        yahoo_player: Dict[str, Any],
        index: Dict[str, Any],
    ) -> Tuple[Optional[str], Optional[float], str]:
        """Resolve a player using previously persisted user/team mapping when valid."""
        if not user_id or not team_key:
            return None, None, "saved mapping unavailable"

        player_key, player_id = self._extract_yahoo_player_identifiers(yahoo_player)
        saved = self.storage.get_saved_player_mapping(
            user_id=user_id,
            team_key=team_key,
            yahoo_player_key=player_key,
            yahoo_player_id=player_id,
        )
        if not saved:
            return None, None, "no saved mapping"

        sleeper_id = str(saved.get("sleeper_id") or "").strip()
        if not sleeper_id:
            return None, None, "saved mapping missing sleeper id"

        if not self._saved_mapping_is_compatible(sleeper_id, yahoo_player, index):
            return None, None, "saved mapping incompatible"

        raw_confidence = saved.get("confidence")
        confidence = 0.99
        if raw_confidence is not None:
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = 0.99

        confidence = max(min(confidence, 1.0), 0.95)
        return sleeper_id, confidence, "saved mapping"

    async def match_player(
        self,
        yahoo_player: Dict[str, Any],
        index: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        team_key: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[float], str]:
        """Match a Yahoo roster player to a Sleeper player ID."""
        if index is None:
            index = await self._build_player_index()

        saved_sleeper_id, saved_confidence, saved_reason = self._resolve_saved_mapping(
            user_id=user_id,
            team_key=team_key,
            yahoo_player=yahoo_player,
            index=index,
        )
        if saved_sleeper_id:
            return saved_sleeper_id, saved_confidence, saved_reason

        team = self.normalize_team(yahoo_player.get("team"))
        position = self.normalize_position(yahoo_player.get("position"))

        _, yahoo_player_id = self._extract_yahoo_player_identifiers(yahoo_player)
        if yahoo_player_id:
            yahoo_id_lookup = index.get("yahoo_id", {})
            yahoo_id_candidates = yahoo_id_lookup.get(yahoo_player_id, [])
            candidate = self._pick_candidate(yahoo_id_candidates, index.get("meta", {}), team, position)
            if candidate:
                if len(yahoo_id_candidates) == 1:
                    return candidate, 1.0, "exact yahoo_id match"
                return candidate, 0.99, "yahoo_id match resolved by team/position"

        if position == "DEF" and team:
            def_team_lookup = index.get("def_by_team", {})
            def_team_candidates = def_team_lookup.get(team, [])
            candidate = self._pick_candidate(def_team_candidates, index.get("meta", {}), team, "DEF")
            if candidate:
                return candidate, 0.99, "defense matched by team"

        name = self.normalize_name(yahoo_player.get("name", ""))
        if not name:
            return None, None, "missing player name"

        name_team = index.get("name_team", {})
        name_pos = index.get("name_pos", {})
        name_only = index.get("name_only", {})
        name_team_compact = index.get("name_team_compact", {})
        name_pos_compact = index.get("name_pos_compact", {})
        name_only_compact = index.get("name_only_compact", {})
        meta = index.get("meta", {})
        compact_name = self.normalize_name_compact(name)

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

        exact_compact_team_candidates = (
            name_team_compact.get((compact_name, team), []) if compact_name and team else []
        )
        candidate = self._pick_candidate(exact_compact_team_candidates, meta, team, position)
        if candidate:
            return candidate, 0.99, "compact name+team match"

        exact_compact_pos_candidates = (
            name_pos_compact.get((compact_name, position), []) if compact_name and position else []
        )
        candidate = self._pick_candidate(exact_compact_pos_candidates, meta, team, position)
        if candidate:
            return candidate, 0.96, "compact name+position match"

        strict_compact_candidates = name_only_compact.get(compact_name, []) if compact_name else []
        candidate = self._pick_candidate(strict_compact_candidates, meta, team, position)
        if candidate:
            confidence = 0.94 if len(strict_compact_candidates) == 1 else 0.91
            reason = (
                "compact name unique match"
                if len(strict_compact_candidates) == 1
                else "compact name best-match"
            )
            return candidate, confidence, reason

        fuzzy_matches = difflib.get_close_matches(name, index.get("names", []), n=1, cutoff=0.92)
        if fuzzy_matches:
            fuzzy_name = fuzzy_matches[0]
            fuzzy_candidates = name_only.get(fuzzy_name, [])
            candidate = self._pick_candidate(fuzzy_candidates, meta, team, position)
            if candidate:
                return candidate, 0.92, f"fuzzy name match ({fuzzy_name})"

        fuzzy_compact = difflib.get_close_matches(
            compact_name,
            index.get("compact_names", []),
            n=1,
            cutoff=0.9,
        )
        if fuzzy_compact:
            fuzzy_compact_name = fuzzy_compact[0]
            fuzzy_compact_candidates = name_only_compact.get(fuzzy_compact_name, [])
            candidate = self._pick_candidate(fuzzy_compact_candidates, meta, team, position)
            if candidate:
                return candidate, 0.9, f"fuzzy compact name match ({fuzzy_compact_name})"

        if team and position:
            team_pos_candidates = [
                sid
                for sid, player_meta in meta.items()
                if player_meta.get("team") == team and player_meta.get("position") == position
            ]
            if team_pos_candidates:
                scored_candidates: List[Tuple[float, str]] = []
                for sid in team_pos_candidates:
                    player_meta = meta.get(sid, {})
                    normalized_names = player_meta.get("normalized_names", [])
                    compact_names = player_meta.get("compact_names", [])

                    best_similarity = 0.0
                    for normalized_candidate_name in normalized_names:
                        best_similarity = max(
                            best_similarity,
                            difflib.SequenceMatcher(None, name, normalized_candidate_name).ratio(),
                        )

                    for compact_candidate_name in compact_names:
                        if compact_name and compact_candidate_name:
                            best_similarity = max(
                                best_similarity,
                                difflib.SequenceMatcher(
                                    None,
                                    compact_name,
                                    compact_candidate_name,
                                ).ratio(),
                            )

                    scored_candidates.append((best_similarity, sid))

                scored_candidates.sort(reverse=True)
                best_similarity, best_sid = scored_candidates[0]
                if best_similarity >= 0.86:
                    return (
                        best_sid,
                        0.88,
                        f"team+position similarity fallback ({best_similarity:.2f})",
                    )

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
        user_id: str,
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
        index = await self._build_player_index()

        for yahoo_player in roster:
            sleeper_id, confidence, match_reason = await self.match_player(
                yahoo_player=yahoo_player,
                index=index,
                user_id=user_id,
                team_key=team_key,
            )
            enhanced_player = None
            if sleeper_id:
                enhanced_player = await self.build_enhanced_player(sleeper_id, preferences.scoring)
                if enhanced_player:
                    yahoo_player_key, yahoo_player_id = self._extract_yahoo_player_identifiers(
                        yahoo_player
                    )
                    self.storage.save_player_mapping(
                        user_id=user_id,
                        team_key=team_key,
                        yahoo_player_key=yahoo_player_key,
                        yahoo_player_id=yahoo_player_id,
                        sleeper_id=sleeper_id,
                        confidence=confidence,
                        match_reason=match_reason,
                    )

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
