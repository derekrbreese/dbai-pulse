"""
Fantasy Football Calculator ADP client for dbAI Pulse.

Fetches Average Draft Position (ADP) data from Fantasy Football Calculator:
https://fantasyfootballcalculator.com/api/v1/adp

No auth required.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

# In-memory cache: keyed by year/teams/scoring/position
_adp_cache: TTLCache = TTLCache(maxsize=200, ttl=get_settings().adp_cache_ttl)


class ADPService:
    """Client/service for Fantasy Football Calculator ADP endpoint."""

    def __init__(self) -> None:
        self.base_url = "https://fantasyfootballcalculator.com/api/v1"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def fetch_adp(
        self,
        year: int,
        teams: int = 12,
        scoring: str = "ppr",
        position: str = "all",
    ) -> Dict[str, Any]:
        """
        Fetch ADP data from Fantasy Football Calculator. Cached for sleeper_cache_ttl.

        FFC params:
        - format: json
        - year: int (e.g., 2025)
        - teams: int (e.g., 12)
        - scoring: standard | half-ppr | ppr
        - position: all | qb | rb | wr | te | k | dst
        """
        cache_key = f"adp_{year}_{teams}_{scoring}_{position}"
        if cache_key in _adp_cache:
            return _adp_cache[cache_key]

        url = f"{self.base_url}/adp/{scoring}"
        params = {
            "teams": teams,
            "year": year,
        }
        if position != "all":
            params["position"] = position

        logger.info(
            "Fetching ADP from FFC: year=%s teams=%s scoring=%s position=%s",
            year,
            teams,
            scoring,
            position,
        )

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, dict):
                logger.warning("Unexpected FFC ADP response shape (not a JSON object)")
                return {}

            _adp_cache[cache_key] = data
            return data
        except Exception as e:
            logger.error(f"Failed to fetch ADP data: {e}")
            return {}

    async def get_adp_players(
        self,
        year: int,
        teams: int = 12,
        scoring: str = "ppr",
        position: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Get list of players with ADP data.

        Returns list of player dicts with keys like:
        - name: player name
        - position: QB, RB, WR, TE, etc.
        - adp: average draft position
        - std_dev: standard deviation
        - high: highest pick
        - low: lowest pick
        """
        data = await self.fetch_adp(year, teams, scoring, position)
        return data.get("players", [])

    async def get_player_adp(
        self,
        player_name: str,
        year: int,
        teams: int = 12,
        scoring: str = "ppr",
    ) -> Optional[Dict[str, Any]]:
        """
        Get ADP data for a specific player by name.

        Returns player ADP dict or None if not found.
        """
        players = await self.get_adp_players(year, teams, scoring)

        # Normalize search
        player_name_lower = player_name.lower()

        for player in players:
            if player.get("name", "").lower() == player_name_lower:
                return player

        # Fuzzy match - check if search term is in player name
        for player in players:
            if player_name_lower in player.get("name", "").lower():
                return player

        return None


# Singleton instance
_service: Optional[ADPService] = None


def get_adp_service() -> ADPService:
    """Get or create ADP service singleton."""
    global _service
    if _service is None:
        _service = ADPService()
    return _service
