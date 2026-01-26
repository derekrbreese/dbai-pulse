"""
Yahoo Fantasy Sports API service for dbAI Pulse.

Uses YFPY library for Yahoo Fantasy API access with OAuth 2.0.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

# Thread pool for running sync YFPY calls
_executor = ThreadPoolExecutor(max_workers=2)

# Cache for league/roster data
_leagues_cache: TTLCache = TTLCache(maxsize=10, ttl=get_settings().sleeper_cache_ttl)
_roster_cache: TTLCache = TTLCache(maxsize=50, ttl=get_settings().sleeper_cache_ttl)


class YahooFantasyService:
    """Service for Yahoo Fantasy Sports API access."""

    def __init__(self):
        self.settings = get_settings()
        self._token_data: Optional[Dict[str, Any]] = None
        self._query = None

    def set_token_data(self, token_data: Dict[str, Any]) -> None:
        """
        Store OAuth token data for current session.
        
        Args:
            token_data: Dict containing access_token, refresh_token, consumer_key, etc.
        """
        self._token_data = token_data
        self._query = None  # Reset query instance to use new tokens
        logger.info("Yahoo OAuth token data updated")

    def get_token_data(self) -> Optional[Dict[str, Any]]:
        """Get stored token data."""
        return self._token_data

    def is_authenticated(self) -> bool:
        """Check if valid token exists."""
        if not self._token_data:
            return False
        
        # Check for required fields
        required_fields = ["access_token", "refresh_token", "consumer_key", "consumer_secret"]
        return all(field in self._token_data for field in required_fields)

    def _get_query(self, league_id: Optional[str] = None):
        """
        Get or create YFPY query instance.
        
        Note: YFPY handles token refresh automatically.
        """
        if not self.is_authenticated():
            raise ValueError("Not authenticated with Yahoo. Please connect your Yahoo account.")

        # Import here to avoid issues if yfpy not installed
        try:
            from yfpy.query import YahooFantasySportsQuery
        except ImportError:
            raise ImportError("yfpy package not installed. Run: pip install yfpy")

        # Create new query instance
        query = YahooFantasySportsQuery(
            league_id=league_id or "0",  # Placeholder if no league specified
            game_code="nfl",
            yahoo_access_token_json=self._token_data,
            browser_callback=False,  # We handle OAuth flow ourselves
            all_output_as_json_str=False,
        )
        
        return query

    async def get_user_games(self) -> List[Dict[str, Any]]:
        """
        Get all NFL fantasy games the user has participated in.
        
        Returns:
            List of game dicts with game_id, season, etc.
        """
        def _fetch():
            query = self._get_query()
            return query.get_all_yahoo_fantasy_game_keys()

        loop = asyncio.get_event_loop()
        try:
            games = await loop.run_in_executor(_executor, _fetch)
            return [{"game_key": str(g)} for g in games] if games else []
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo games: {e}")
            raise

    async def get_user_leagues(self, game_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all user's fantasy football leagues for a season.
        
        Args:
            game_id: Yahoo game ID for specific season (e.g., 449 for 2024)
                    If None, gets current season leagues.
        
        Returns:
            List of league dicts with league_id, name, etc.
        """
        cache_key = f"leagues_{game_id}"
        if cache_key in _leagues_cache:
            return _leagues_cache[cache_key]

        def _fetch():
            query = self._get_query()
            if game_id:
                return query.get_user_leagues_by_game_key(game_id)
            return query.get_user_leagues()

        loop = asyncio.get_event_loop()
        try:
            leagues = await loop.run_in_executor(_executor, _fetch)
            
            # Convert to dicts
            result = []
            if leagues:
                for league in leagues:
                    league_dict = {
                        "league_id": getattr(league, "league_id", None),
                        "league_key": getattr(league, "league_key", None),
                        "name": getattr(league, "name", "Unknown League"),
                        "num_teams": getattr(league, "num_teams", 0),
                        "season": getattr(league, "season", None),
                        "draft_status": getattr(league, "draft_status", None),
                    }
                    result.append(league_dict)
            
            _leagues_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo leagues: {e}")
            raise

    async def get_user_teams(self) -> List[Dict[str, Any]]:
        """
        Get all teams the user owns across leagues.
        
        Returns:
            List of team dicts with team_id, league_id, name, etc.
        """
        def _fetch():
            query = self._get_query()
            return query.get_user_teams()

        loop = asyncio.get_event_loop()
        try:
            teams = await loop.run_in_executor(_executor, _fetch)
            
            result = []
            if teams:
                for team in teams:
                    team_dict = {
                        "team_id": getattr(team, "team_id", None),
                        "team_key": getattr(team, "team_key", None),
                        "name": getattr(team, "name", "Unknown Team"),
                        "league_key": getattr(team, "league_key", None),
                    }
                    result.append(team_dict)
            
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Yahoo teams: {e}")
            raise

    async def get_team_roster(
        self, league_id: str, team_id: str, week: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get roster for a specific team.
        
        Args:
            league_id: Yahoo league ID
            team_id: Yahoo team ID within the league
            week: Optional week number for historical roster
        
        Returns:
            List of player dicts with player_id, name, position, etc.
        """
        cache_key = f"roster_{league_id}_{team_id}_{week}"
        if cache_key in _roster_cache:
            return _roster_cache[cache_key]

        def _fetch():
            query = self._get_query(league_id)
            if week:
                return query.get_team_roster_player_info_by_week(team_id, week)
            return query.get_team_roster_player_stats(team_id)

        loop = asyncio.get_event_loop()
        try:
            roster = await loop.run_in_executor(_executor, _fetch)
            
            result = []
            if roster:
                for player in roster:
                    player_dict = {
                        "player_id": getattr(player, "player_id", None),
                        "player_key": getattr(player, "player_key", None),
                        "name": getattr(player, "name", {}).get("full", "Unknown"),
                        "position": getattr(player, "display_position", None),
                        "team": getattr(player, "editorial_team_abbr", None),
                        "status": getattr(player, "status", None),
                        "injury_status": getattr(player, "injury_status", None),
                    }
                    result.append(player_dict)
            
            _roster_cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Failed to fetch team roster: {e}")
            raise

    async def get_league_draft_results(self, league_id: str) -> List[Dict[str, Any]]:
        """
        Get draft results for a league.
        
        Args:
            league_id: Yahoo league ID
        
        Returns:
            List of draft pick dicts with pick, round, player_key, team_key
        """
        def _fetch():
            query = self._get_query(league_id)
            return query.get_league_draft_results()

        loop = asyncio.get_event_loop()
        try:
            draft_results = await loop.run_in_executor(_executor, _fetch)
            
            result = []
            if draft_results:
                for pick in draft_results:
                    pick_dict = {
                        "pick": getattr(pick, "pick", None),
                        "round": getattr(pick, "round", None),
                        "player_key": getattr(pick, "player_key", None),
                        "team_key": getattr(pick, "team_key", None),
                    }
                    result.append(pick_dict)
            
            return result
        except Exception as e:
            logger.error(f"Failed to fetch draft results: {e}")
            raise

    async def get_player_details(
        self, league_id: str, player_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific player.
        
        Args:
            league_id: Yahoo league ID
            player_key: Yahoo player key (e.g., "449.p.33389")
        
        Returns:
            Player dict with full details
        """
        def _fetch():
            query = self._get_query(league_id)
            return query.get_player_stats_for_season(player_key)

        loop = asyncio.get_event_loop()
        try:
            player = await loop.run_in_executor(_executor, _fetch)
            
            if not player:
                return None
            
            return {
                "player_id": getattr(player, "player_id", None),
                "player_key": getattr(player, "player_key", None),
                "name": getattr(player, "name", {}).get("full", "Unknown"),
                "position": getattr(player, "display_position", None),
                "team": getattr(player, "editorial_team_abbr", None),
                "percent_owned": getattr(player, "percent_owned", {}).get("value", 0),
            }
        except Exception as e:
            logger.error(f"Failed to fetch player details: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear all cached data."""
        _leagues_cache.clear()
        _roster_cache.clear()
        logger.info("Yahoo Fantasy cache cleared")


# Singleton instance
_service: Optional[YahooFantasyService] = None


def get_yahoo_service() -> YahooFantasyService:
    """Get or create Yahoo Fantasy service singleton."""
    global _service
    if _service is None:
        _service = YahooFantasyService()
    return _service
