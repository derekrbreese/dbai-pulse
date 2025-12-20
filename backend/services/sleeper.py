"""
Sleeper API client for dbAI Pulse.

Handles player data, projections, and stats from the Sleeper API.
Free, no auth required.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx
from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

# In-memory caches
_players_cache: Optional[Dict[str, Any]] = None
_projections_cache: TTLCache = TTLCache(
    maxsize=100, ttl=get_settings().sleeper_cache_ttl
)
_stats_cache: TTLCache = TTLCache(maxsize=500, ttl=get_settings().sleeper_cache_ttl)


class SleeperClient:
    """Client for Sleeper API."""

    def __init__(self):
        self.base_url = get_settings().sleeper_base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def get_all_players(self) -> Dict[str, Any]:
        """
        Get all NFL players. Cached indefinitely (player database doesn't change often).
        Returns dict keyed by Sleeper player ID.
        """
        global _players_cache

        if _players_cache is not None:
            return _players_cache

        logger.info("Fetching all players from Sleeper API...")
        response = await self.client.get(f"{self.base_url}/players/nfl")
        response.raise_for_status()
        _players_cache = response.json()
        logger.info(f"Cached {len(_players_cache)} players")
        return _players_cache

    async def search_players(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search players by name.
        Returns list of matching players.
        """
        players = await self.get_all_players()
        query_lower = query.lower()

        results = []
        for player_id, player in players.items():
            # Skip non-skill positions
            position = player.get("position", "")
            if position not in ("QB", "RB", "WR", "TE", "K", "DEF"):
                continue

            # Check name match
            full_name = (
                f"{player.get('first_name', '')} {player.get('last_name', '')}".lower()
            )
            search_name = player.get("search_full_name", "").lower()

            if query_lower in full_name or query_lower in search_name:
                results.append(
                    {
                        "sleeper_id": player_id,
                        "name": f"{player.get('first_name', '')} {player.get('last_name', '')}",
                        "position": position,
                        "team": player.get("team"),
                        "bye_week": player.get("bye_week"),
                    }
                )

        # Sort by relevance (exact match first, then alphabetical)
        results.sort(
            key=lambda p: (0 if query_lower == p["name"].lower() else 1, p["name"])
        )

        return results[:limit]

    async def get_player(self, sleeper_id: str) -> Optional[Dict[str, Any]]:
        """Get a single player by Sleeper ID."""
        players = await self.get_all_players()
        player = players.get(sleeper_id)

        if not player:
            return None

        return {
            "sleeper_id": sleeper_id,
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}",
            "position": player.get("position", ""),
            "team": player.get("team"),
            "bye_week": player.get("bye_week"),
        }

    async def get_active_players_by_position(
        self, position: Optional[str] = None, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get active NFL players, optionally filtered by position.
        Returns players with teams (active) sorted by search rank.
        """
        players = await self.get_all_players()
        valid_positions = ("QB", "RB", "WR", "TE", "K", "DEF")

        results = []
        for player_id, player in players.items():
            pos = player.get("position", "")
            team = player.get("team")

            # Only active players with teams
            if not team or pos not in valid_positions:
                continue

            # Position filter
            if position and pos != position:
                continue

            results.append(
                {
                    "sleeper_id": player_id,
                    "name": f"{player.get('first_name', '')} {player.get('last_name', '')}",
                    "position": pos,
                    "team": team,
                    "bye_week": player.get("bye_week"),
                    "search_rank": player.get("search_rank") or 9999,
                }
            )

        # Sort by search rank (lower = more relevant), handle None
        results.sort(key=lambda p: p.get("search_rank") or 9999)
        return results[:limit]

    async def get_projections(self, season: int, week: int) -> Dict[str, Any]:
        """
        Get weekly projections for all players.
        Cached for sleeper_cache_ttl.
        """
        cache_key = f"proj_{season}_{week}"

        if cache_key in _projections_cache:
            return _projections_cache[cache_key]

        logger.info(f"Fetching projections for {season} week {week}...")
        url = f"{self.base_url}/projections/nfl/{season}/{week}"
        response = await self.client.get(url)

        if response.status_code == 404:
            logger.warning(f"No projections found for {season} week {week}")
            return {}

        response.raise_for_status()
        data = response.json()
        _projections_cache[cache_key] = data
        return data

    async def get_player_projection(
        self, sleeper_id: str, season: int, week: int
    ) -> float:
        """Get projection for a specific player."""
        projections = await self.get_projections(season, week)
        player_proj = projections.get(sleeper_id, {})

        # Sleeper API structure: player_id -> {stats: {...}, player: {...}}
        # The stats object contains the actual projection numbers
        stats = player_proj.get(
            "stats", player_proj
        )  # Fallback to player_proj if stats not nested

        # Try PPR first, then half-PPR, then standard
        pts = (
            stats.get("pts_ppr")
            or stats.get("pts_half_ppr")
            or stats.get("pts_std")
            or stats.get("pts")
            or 0.0
        )
        return float(pts)

    async def get_stats(self, season: int, week: int) -> Dict[str, Any]:
        """
        Get actual stats for a week.
        Cached for sleeper_cache_ttl.
        """
        cache_key = f"stats_{season}_{week}"

        if cache_key in _stats_cache:
            return _stats_cache[cache_key]

        logger.info(f"Fetching stats for {season} week {week}...")
        url = f"{self.base_url}/stats/nfl/regular/{season}/{week}"
        response = await self.client.get(url)

        if response.status_code == 404:
            logger.warning(f"No stats found for {season} week {week}")
            return {}

        response.raise_for_status()
        data = response.json()
        _stats_cache[cache_key] = data
        return data

    async def get_player_stats(
        self, sleeper_id: str, season: int, week: int
    ) -> Optional[Dict[str, Any]]:
        """Get actual stats for a specific player in a week."""
        stats = await self.get_stats(season, week)
        return stats.get(sleeper_id)

    async def get_recent_performance(
        self, sleeper_id: str, season: int, current_week: int, lookback: int = 3
    ) -> Dict[str, Any]:
        """
        Get recent performance stats for a player.
        Returns avg points, weekly points, and trend.
        """
        weekly_points = []

        for i in range(1, lookback + 1):
            week = current_week - i
            if week < 1:
                break

            stats = await self.get_player_stats(sleeper_id, season, week)
            if stats:
                # Stats can be nested under "stats" key or directly in the object
                stat_data = stats.get("stats", stats)
                points = (
                    stat_data.get("pts_ppr")
                    or stat_data.get("pts_half_ppr")
                    or stat_data.get("pts_std")
                    or stat_data.get("pts")
                    or 0
                )
                weekly_points.append({"week": week, "points": float(points)})

        if not weekly_points:
            return {
                "weeks_analyzed": 0,
                "avg_points": 0.0,
                "total_points": 0.0,
                "trend": "stable",
                "weekly_points": [],
            }

        total = sum(w["points"] for w in weekly_points)
        avg = total / len(weekly_points)

        # Calculate trend
        trend = "stable"
        if len(weekly_points) >= 2:
            recent = weekly_points[0]["points"]  # Most recent
            previous_avg = sum(w["points"] for w in weekly_points[1:]) / len(
                weekly_points[1:]
            )
            if previous_avg > 0:
                change = (recent - previous_avg) / previous_avg
                if change > 0.25:
                    trend = "improving"
                elif change < -0.25:
                    trend = "declining"

        return {
            "weeks_analyzed": len(weekly_points),
            "avg_points": round(avg, 1),
            "total_points": round(total, 1),
            "trend": trend,
            "weekly_points": [w["points"] for w in weekly_points],
        }


# Singleton instance
_client: Optional[SleeperClient] = None


def get_sleeper_client() -> SleeperClient:
    """Get or create Sleeper client singleton."""
    global _client
    if _client is None:
        _client = SleeperClient()
    return _client
