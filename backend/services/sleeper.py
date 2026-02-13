"""
Sleeper API client for dbAI Pulse.

Handles player data, projections, and stats from the Sleeper API.
Free, no auth required.
"""

import asyncio
import logging
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

import httpx
from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

_SETTINGS = get_settings()
REQUEST_TIMEOUT_SECONDS = 10.0
CONNECT_TIMEOUT_SECONDS = 5.0
RETRY_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 0.35
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
VALID_SKILL_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K', 'DEF')

PLAYERS_CACHE_TTL_SECONDS = max(6 * 60 * 60, _SETTINGS.sleeper_cache_ttl * 12)
STATE_CACHE_TTL_SECONDS = min(_SETTINGS.sleeper_cache_ttl, 60)

_MISSING = object()

# In-memory caches
_players_cache: TTLCache = TTLCache(maxsize=1, ttl=PLAYERS_CACHE_TTL_SECONDS)
_projections_cache: TTLCache = TTLCache(maxsize=100, ttl=_SETTINGS.sleeper_cache_ttl)
_stats_cache: TTLCache = TTLCache(maxsize=500, ttl=_SETTINGS.sleeper_cache_ttl)
_state_cache: TTLCache = TTLCache(maxsize=1, ttl=STATE_CACHE_TTL_SECONDS)

# Last-known-good payload fallback for degraded reads.
_last_known_good_payloads: Dict[str, Any] = {}


class SleeperClient:
    """Client for Sleeper API."""

    def __init__(self) -> None:
        self.base_url = _SETTINGS.sleeper_base_url.rstrip('/')
        self.max_retries = RETRY_ATTEMPTS
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        """Safely coerce values to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_player_name(player: Dict[str, Any], fallback_id: str) -> str:
        """Build a stable display name for a player payload."""
        first_name = str(player.get('first_name') or '').strip()
        last_name = str(player.get('last_name') or '').strip()
        full_name = f'{first_name} {last_name}'.strip()

        if full_name:
            return full_name

        fallback_name = player.get('full_name') or player.get('search_full_name')
        if fallback_name:
            return str(fallback_name).strip()

        return fallback_id

    @staticmethod
    def _normalize_player_summary(
        sleeper_id: str,
        player: Dict[str, Any],
        include_search_rank: bool = False,
    ) -> Dict[str, Any]:
        """Normalize a raw Sleeper player payload into dbAI Pulse response shape."""
        normalized = {
            'sleeper_id': str(sleeper_id),
            'name': SleeperClient._build_player_name(player, fallback_id=str(sleeper_id)),
            'position': str(player.get('position') or ''),
            'team': player.get('team'),
            'bye_week': SleeperClient._coerce_int(player.get('bye_week')),
            'espn_id': str(player.get('espn_id')) if player.get('espn_id') else None,
        }

        if include_search_rank:
            rank = SleeperClient._coerce_int(player.get('search_rank'))
            normalized['search_rank'] = rank if rank is not None else 9999

        return normalized

    @staticmethod
    def _cache_lookup(cache: TTLCache, cache_key: str) -> Any:
        """Read from cache while preserving empty dict/list values."""
        return cache.get(cache_key, _MISSING)

    @staticmethod
    def _record_last_known_good(cache_key: str, payload: Any) -> None:
        """Store last-known-good payload for degraded mode fallback."""
        _last_known_good_payloads[cache_key] = payload

    @staticmethod
    def _get_last_known_good(cache_key: str) -> Any:
        """Get previously successful payload if available."""
        return _last_known_good_payloads.get(cache_key, _MISSING)

    @staticmethod
    def _retry_backoff_seconds(attempt: int) -> float:
        """Compute exponential backoff delay."""
        return BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))

    async def _request_json(self, endpoint: str, allow_404: bool = False) -> Optional[Any]:
        """Perform GET request with retry, timeout, and structured logging."""
        normalized_endpoint = endpoint if endpoint.startswith('/') else f'/{endpoint}'
        url = f'{self.base_url}{normalized_endpoint}'

        for attempt in range(1, self.max_retries + 1):
            started = perf_counter()
            try:
                response = await self.client.get(url)
                latency_ms = (perf_counter() - started) * 1000
                status_code = response.status_code

                if status_code == 404 and allow_404:
                    logger.info(
                        'Sleeper 404 endpoint=%s status=%s latency_ms=%.1f attempt=%d',
                        normalized_endpoint,
                        status_code,
                        latency_ms,
                        attempt,
                    )
                    return None

                if (
                    status_code in RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                ):
                    backoff_seconds = self._retry_backoff_seconds(attempt)
                    logger.warning(
                        'Sleeper retryable status endpoint=%s status=%s latency_ms=%.1f '
                        'attempt=%d/%d backoff_s=%.2f',
                        normalized_endpoint,
                        status_code,
                        latency_ms,
                        attempt,
                        self.max_retries,
                        backoff_seconds,
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                response.raise_for_status()

                logger.debug(
                    'Sleeper success endpoint=%s status=%s latency_ms=%.1f attempt=%d',
                    normalized_endpoint,
                    status_code,
                    latency_ms,
                    attempt,
                )

                try:
                    return response.json()
                except ValueError as exc:
                    raise RuntimeError(
                        f'Invalid JSON from Sleeper endpoint {normalized_endpoint}'
                    ) from exc
            except httpx.RequestError as exc:
                latency_ms = (perf_counter() - started) * 1000
                if attempt < self.max_retries:
                    backoff_seconds = self._retry_backoff_seconds(attempt)
                    logger.warning(
                        'Sleeper request error endpoint=%s latency_ms=%.1f '
                        'attempt=%d/%d backoff_s=%.2f error=%s',
                        normalized_endpoint,
                        latency_ms,
                        attempt,
                        self.max_retries,
                        backoff_seconds,
                        exc,
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                logger.error(
                    'Sleeper request failed endpoint=%s attempt=%d error=%s',
                    normalized_endpoint,
                    attempt,
                    exc,
                    exc_info=True,
                )
                raise
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                latency_ms = (perf_counter() - started) * 1000

                if status_code in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    backoff_seconds = self._retry_backoff_seconds(attempt)
                    logger.warning(
                        'Sleeper HTTP retry endpoint=%s status=%s latency_ms=%.1f '
                        'attempt=%d/%d backoff_s=%.2f',
                        normalized_endpoint,
                        status_code,
                        latency_ms,
                        attempt,
                        self.max_retries,
                        backoff_seconds,
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                logger.error(
                    'Sleeper HTTP failure endpoint=%s status=%s latency_ms=%.1f attempt=%d',
                    normalized_endpoint,
                    status_code,
                    latency_ms,
                    attempt,
                    exc_info=True,
                )
                raise

        return None

    async def get_all_players(self) -> Dict[str, Any]:
        """
        Get all NFL players.

        Cached with long TTL and stored as last-known-good fallback.
        Returns dict keyed by Sleeper player ID.
        """
        cache_key = 'players_nfl'
        cached = self._cache_lookup(_players_cache, cache_key)
        if cached is not _MISSING:
            return cached

        logger.info('Fetching all players from Sleeper API...')
        try:
            players = await self._request_json('/players/nfl')
        except Exception as exc:
            stale_payload = self._get_last_known_good(cache_key)
            if stale_payload is not _MISSING:
                logger.warning(
                    'Using last-known-good players payload after fetch failure: %s',
                    exc,
                )
                return stale_payload
            raise

        if not isinstance(players, dict):
            raise RuntimeError('Unexpected Sleeper players response shape')

        _players_cache[cache_key] = players
        self._record_last_known_good(cache_key, players)
        logger.info('Cached %d players', len(players))
        return players

    async def get_nfl_state(self) -> Dict[str, Any]:
        """Get current NFL state payload."""
        cache_key = 'nfl_state'
        cached = self._cache_lookup(_state_cache, cache_key)
        if cached is not _MISSING:
            return cached

        try:
            data = await self._request_json('/state/nfl')
        except Exception as exc:
            stale_payload = self._get_last_known_good(cache_key)
            if stale_payload is not _MISSING:
                logger.warning(
                    'Using last-known-good nfl state after fetch failure: %s',
                    exc,
                )
                return stale_payload
            raise

        if not isinstance(data, dict):
            raise RuntimeError('Unexpected Sleeper nfl state response shape')

        _state_cache[cache_key] = data
        self._record_last_known_good(cache_key, data)
        return data

    async def get_current_season_week(
        self, fallback_season: int, fallback_week: int
    ) -> Tuple[int, int]:
        """Resolve current season/week with safe fallback to configured defaults."""
        try:
            state = await self.get_nfl_state()
            season = self._coerce_int(state.get('season'))
            week = self._coerce_int(state.get('week'))
            season_type = state.get('season_type')

            if season_type and season_type != 'regular':
                return fallback_season, fallback_week
            if season is None or week is None:
                return fallback_season, fallback_week

            return season, week
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to resolve current season/week: %s', exc)
            return fallback_season, fallback_week

    async def get_current_season_context(
        self, fallback_season: int, fallback_week: int
    ) -> Tuple[int, int, str]:
        """Return (season, week, season_type). Falls back to 'off' on error."""
        try:
            state = await self.get_nfl_state()
            season = self._coerce_int(state.get('season')) or fallback_season
            week = self._coerce_int(state.get('week')) or fallback_week
            season_type = state.get('season_type') or 'off'
            return season, week, season_type
        except Exception as exc:  # noqa: BLE001
            logger.warning('Failed to resolve season context: %s', exc)
            return fallback_season, fallback_week, 'off'

    async def search_players(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search players by name.

        Returns list of matching players.
        """
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        players = await self.get_all_players()
        results: List[Dict[str, Any]] = []

        for player_id, player in players.items():
            position = str(player.get('position') or '')
            if position not in VALID_SKILL_POSITIONS:
                continue

            name = self._build_player_name(player, fallback_id=str(player_id)).lower()
            search_name = str(player.get('search_full_name') or '').lower()

            if query_lower in name or query_lower in search_name:
                results.append(self._normalize_player_summary(str(player_id), player))

        # Sort by relevance (exact match first, then alphabetical)
        results.sort(
            key=lambda p: (0 if query_lower == str(p['name']).lower() else 1, p['name'])
        )

        return results[:limit]

    async def get_player(self, sleeper_id: str) -> Optional[Dict[str, Any]]:
        """Get a single player by Sleeper ID."""
        normalized_id = str(sleeper_id)
        players = await self.get_all_players()
        player = players.get(normalized_id)

        if not player:
            return None

        return self._normalize_player_summary(normalized_id, player)

    async def get_active_players_by_position(
        self, position: Optional[str] = None, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get active NFL players, optionally filtered by position.

        Returns players with teams (active) sorted by search rank.
        """
        players = await self.get_all_players()
        position_filter = position.upper() if position else None

        results: List[Dict[str, Any]] = []
        for player_id, player in players.items():
            pos = str(player.get('position') or '')
            team = player.get('team')

            # Only active players with teams
            if not team or pos not in VALID_SKILL_POSITIONS:
                continue

            # Position filter
            if position_filter and pos != position_filter:
                continue

            results.append(
                self._normalize_player_summary(
                    str(player_id),
                    player,
                    include_search_rank=True,
                )
            )

        # Sort by search rank (lower = more relevant), handle None
        results.sort(key=lambda p: p.get('search_rank') or 9999)
        return results[:limit]

    async def get_projections(self, season: int, week: int) -> Dict[str, Any]:
        """
        Get weekly projections for all players.

        Cached for sleeper_cache_ttl with last-known-good fallback.
        """
        cache_key = f'proj_{season}_{week}'
        cached = self._cache_lookup(_projections_cache, cache_key)
        if cached is not _MISSING:
            return cached

        logger.info('Fetching projections for %s week %s...', season, week)
        endpoint = f'/projections/nfl/{season}/{week}'
        try:
            data = await self._request_json(endpoint, allow_404=True)
        except Exception as exc:
            stale_payload = self._get_last_known_good(cache_key)
            if stale_payload is not _MISSING:
                logger.warning(
                    'Using last-known-good projections for %s week %s: %s',
                    season,
                    week,
                    exc,
                )
                return stale_payload
            raise

        if data is None:
            logger.warning('No projections found for %s week %s', season, week)
            _projections_cache[cache_key] = {}
            self._record_last_known_good(cache_key, {})
            return {}

        if not isinstance(data, dict):
            raise RuntimeError('Unexpected Sleeper projections response shape')

        _projections_cache[cache_key] = data
        self._record_last_known_good(cache_key, data)
        return data

    async def get_player_projection(
        self, sleeper_id: str, season: int, week: int, scoring: str = 'ppr'
    ) -> float:
        """Get projection for a specific player."""
        normalized_id = str(sleeper_id)
        projections = await self.get_projections(season, week)
        player_proj = projections.get(normalized_id, {})

        # Sleeper API structure: player_id -> {stats: {...}, player: {...}}
        # The stats object contains the actual projection numbers.
        stats = player_proj.get('stats', player_proj) if player_proj else {}

        pts = self._extract_points_by_scoring(stats, scoring)
        return float(pts)

    @staticmethod
    def _extract_points_by_scoring(stat_data: Dict[str, Any], scoring: str = 'ppr') -> float:
        """Extract points value from stats/projection payload based on scoring mode."""
        if not isinstance(stat_data, dict):
            return 0.0

        scoring_mode = (scoring or 'ppr').lower()
        if scoring_mode == 'half_ppr':
            keys = ('pts_half_ppr', 'pts_ppr', 'pts_std', 'pts')
        elif scoring_mode == 'std':
            keys = ('pts_std', 'pts_half_ppr', 'pts_ppr', 'pts')
        else:
            keys = ('pts_ppr', 'pts_half_ppr', 'pts_std', 'pts')

        for key in keys:
            value = stat_data.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return 0.0

    async def get_stats(self, season: int, week: int) -> Dict[str, Any]:
        """
        Get actual stats for a week.

        Cached for sleeper_cache_ttl with last-known-good fallback.
        """
        cache_key = f'stats_{season}_{week}'
        cached = self._cache_lookup(_stats_cache, cache_key)
        if cached is not _MISSING:
            return cached

        logger.info('Fetching stats for %s week %s...', season, week)
        endpoint = f'/stats/nfl/regular/{season}/{week}'

        try:
            data = await self._request_json(endpoint, allow_404=True)
        except Exception as exc:
            stale_payload = self._get_last_known_good(cache_key)
            if stale_payload is not _MISSING:
                logger.warning(
                    'Using last-known-good stats for %s week %s: %s',
                    season,
                    week,
                    exc,
                )
                return stale_payload
            raise

        if data is None:
            logger.warning('No stats found for %s week %s', season, week)
            _stats_cache[cache_key] = {}
            self._record_last_known_good(cache_key, {})
            return {}

        if not isinstance(data, dict):
            raise RuntimeError('Unexpected Sleeper stats response shape')

        _stats_cache[cache_key] = data
        self._record_last_known_good(cache_key, data)
        return data

    async def get_player_stats(
        self, sleeper_id: str, season: int, week: int
    ) -> Optional[Dict[str, Any]]:
        """Get actual stats for a specific player in a week."""
        normalized_id = str(sleeper_id)
        stats = await self.get_stats(season, week)
        player_stats = stats.get(normalized_id)
        if not isinstance(player_stats, dict):
            return None
        return player_stats

    async def get_recent_performance(
        self,
        sleeper_id: str,
        season: int,
        current_week: int,
        lookback: int = 3,
        scoring: str = 'ppr',
    ) -> Dict[str, Any]:
        """
        Get recent performance stats for a player.

        Returns avg points, weekly points, and trend.
        """
        weekly_points: List[Dict[str, Any]] = []

        for i in range(1, lookback + 1):
            week = current_week - i
            if week < 1:
                break

            stats = await self.get_player_stats(sleeper_id, season, week)
            if stats:
                # Stats can be nested under "stats" key or directly in the object.
                stat_data = stats.get('stats', stats)
                points = self._extract_points_by_scoring(stat_data, scoring)
                weekly_points.append({'week': week, 'points': float(points)})

        if not weekly_points:
            return {
                'weeks_analyzed': 0,
                'avg_points': 0.0,
                'total_points': 0.0,
                'trend': 'stable',
                'weekly_points': [],
            }

        total = sum(w['points'] for w in weekly_points)
        avg = total / len(weekly_points)

        # Calculate trend
        trend = 'stable'
        if len(weekly_points) >= 2:
            recent = weekly_points[0]['points']  # Most recent
            previous_avg = sum(w['points'] for w in weekly_points[1:]) / len(
                weekly_points[1:]
            )
            if previous_avg > 0:
                change = (recent - previous_avg) / previous_avg
                if change > 0.25:
                    trend = 'improving'
                elif change < -0.25:
                    trend = 'declining'

        return {
            'weeks_analyzed': len(weekly_points),
            'avg_points': round(avg, 1),
            'total_points': round(total, 1),
            'trend': trend,
            'weekly_points': [w['points'] for w in weekly_points],
        }

    async def get_recent_projection_avg(
        self,
        sleeper_id: str,
        season: int,
        current_week: int,
        lookback: int = 3,
        scoring: str = 'ppr',
    ) -> float:
        """
        Get average projection over recent weeks.

        Returns 0.0 if no projections are available.
        """
        projections = []

        for i in range(1, lookback + 1):
            week = current_week - i
            if week < 1:
                break

            proj = await self.get_player_projection(
                sleeper_id,
                season,
                week,
                scoring=scoring,
            )
            if proj:
                projections.append(float(proj))

        if not projections:
            return 0.0

        return round(sum(projections) / len(projections), 1)


# Singleton instance
_client: Optional[SleeperClient] = None


def get_sleeper_client() -> SleeperClient:
    """Get or create Sleeper client singleton."""
    global _client
    if _client is None:
        _client = SleeperClient()
    return _client
