"""
Yahoo Fantasy Sports API service for dbAI Pulse.

Uses YFPY library for Yahoo Fantasy API access with OAuth 2.0.
Falls back to direct Yahoo API calls when yfpy model parsing fails.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import httpx
from cachetools import TTLCache

from config import get_settings

logger = logging.getLogger(__name__)

# Thread pool for running sync YFPY calls
_executor = ThreadPoolExecutor(max_workers=4)

# Cache for league/roster data
_leagues_cache: TTLCache = TTLCache(maxsize=50, ttl=get_settings().yahoo_cache_ttl_seconds)
_teams_cache: TTLCache = TTLCache(maxsize=50, ttl=get_settings().yahoo_cache_ttl_seconds)
_roster_cache: TTLCache = TTLCache(maxsize=200, ttl=get_settings().yahoo_cache_ttl_seconds)
_waiver_cache: TTLCache = TTLCache(maxsize=100, ttl=600)


class YahooFantasyService:
    """Service for Yahoo Fantasy Sports API access for a single user token."""

    def __init__(self, token_data: Dict[str, Any], user_id: str):
        self.settings = get_settings()
        self._token_data = dict(token_data)
        self._user_id = user_id

    def get_token_data(self) -> Optional[Dict[str, Any]]:
        """Return current token data (possibly updated by YFPY refresh)."""
        return dict(self._token_data)

    def is_authenticated(self) -> bool:
        """Check if valid token exists."""
        if not self._token_data:
            return False
        
        # Check for required fields
        required_fields = ["access_token", "refresh_token", "consumer_key", "consumer_secret"]
        return all(field in self._token_data for field in required_fields)

    def _user_cache_key(self, *parts: Any) -> str:
        """Build cache keys scoped to the current user."""
        return ":".join([self._user_id, *[str(part) for part in parts]])

    @staticmethod
    def _extract_name(name_value: Any) -> str:
        """Return display name from Yahoo API value variants (handles dict, yfpy objects, str, float)."""
        if isinstance(name_value, str):
            return name_value
        if isinstance(name_value, dict):
            return str(name_value.get("full") or name_value.get("first") or "Unknown")
        # yfpy model objects (e.g. Name) — try attribute access
        full = getattr(name_value, "full", None)
        if full:
            return str(full)
        first = getattr(name_value, "first", None)
        last = getattr(name_value, "last", None)
        if first:
            return f"{first} {last}".strip() if last else str(first)
        return "Unknown"

    @staticmethod
    def _extract_token_from_query(query: Any) -> Optional[Dict[str, Any]]:
        """Extract possibly refreshed token data from YFPY query internals."""
        candidate_attrs = [
            "yahoo_access_token_json",
            "yahoo_access_token_dict",
            "_yahoo_access_token_data",
            "_yahoo_access_token_json",
        ]

        for attr_name in candidate_attrs:
            candidate = getattr(query, attr_name, None)
            if isinstance(candidate, dict) and candidate.get("access_token"):
                return candidate

        oauth2_session = getattr(query, "oauth2_session", None)
        if oauth2_session is not None:
            token = getattr(oauth2_session, "token", None)
            if isinstance(token, dict) and token.get("access_token"):
                return token

        return None

    def _merge_token_update(self, token_update: Optional[Dict[str, Any]]) -> None:
        """Merge refreshed token values into current token dict."""
        if not token_update:
            return

        merged = dict(self._token_data)
        for key, value in token_update.items():
            if value is not None:
                merged[key] = value

        if merged.get("expires"):
            try:
                merged["expires_in"] = int(merged["expires"])
            except (TypeError, ValueError):
                pass

        self._token_data = merged

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
            result = query.get_all_yahoo_fantasy_game_keys()
            return result, self._extract_token_from_query(query)

        loop = asyncio.get_event_loop()
        try:
            games, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)
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
        cache_key = self._user_cache_key("leagues", game_id or "current")
        if cache_key in _leagues_cache:
            return _leagues_cache[cache_key]

        # Try yfpy first, fall back to direct API if yfpy model parsing fails.
        try:
            def _fetch():
                query = self._get_query()
                if game_id:
                    result = query.get_user_leagues_by_game_key(game_id)
                else:
                    result = query.get_user_leagues()
                return result, self._extract_token_from_query(query)

            loop = asyncio.get_event_loop()
            leagues, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)

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
        except Exception as yfpy_err:
            logger.warning("yfpy get_user_leagues failed (%s), using direct API", yfpy_err)

        # Direct Yahoo API fallback
        result = await self._fetch_leagues_direct(game_id)
        _leagues_cache[cache_key] = result
        return result

    async def _fetch_leagues_direct(self, game_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch user leagues via direct Yahoo API call (bypasses yfpy model parsing)."""
        access_token = self._token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token available")

        url = (
            "https://fantasysports.yahooapis.com/fantasy/v2"
            "/users;use_login=1/games;game_keys=nfl/leagues?format=json"
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})

        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Yahoo token expired. Please reconnect.")
        resp.raise_for_status()

        data = resp.json()
        result: List[Dict[str, Any]] = []

        try:
            games = (
                data.get("fantasy_content", {})
                .get("users", {}).get("0", {})
                .get("user", [{}])
            )
            # user payload is a list; find the games block
            games_block = None
            for item in (games if isinstance(games, list) else [games]):
                if isinstance(item, dict) and "games" in item:
                    games_block = item["games"]
                    break

            if not games_block:
                return result

            for gkey, gval in games_block.items():
                if gkey == "count" or not isinstance(gval, dict):
                    continue
                game_list = gval.get("game", [])
                if not isinstance(game_list, list):
                    continue
                for entry in game_list:
                    if not isinstance(entry, dict) or "leagues" not in entry:
                        continue
                    leagues_block = entry["leagues"]
                    for lkey, lval in leagues_block.items():
                        if lkey == "count" or not isinstance(lval, dict):
                            continue
                        league_info_list = lval.get("league", [])
                        if not isinstance(league_info_list, list):
                            continue
                        # league data is spread across list elements
                        league_id = None
                        league_key = None
                        league_name = "Unknown League"
                        num_teams = 0
                        season = None
                        draft_status = None
                        for part in league_info_list:
                            if isinstance(part, list):
                                for sub in part:
                                    if isinstance(sub, dict):
                                        if "league_id" in sub:
                                            league_id = str(sub["league_id"])
                                        if "league_key" in sub:
                                            league_key = str(sub["league_key"])
                                        if "name" in sub:
                                            league_name = str(sub["name"])
                                        if "num_teams" in sub:
                                            num_teams = int(sub["num_teams"])
                                        if "season" in sub:
                                            season = str(sub["season"])
                                        if "draft_status" in sub:
                                            draft_status = str(sub["draft_status"])
                            elif isinstance(part, dict):
                                if "league_id" in part:
                                    league_id = str(part["league_id"])
                                if "league_key" in part:
                                    league_key = str(part["league_key"])
                                if "name" in part:
                                    league_name = str(part["name"])
                                if "num_teams" in part:
                                    num_teams = int(part["num_teams"])
                                if "season" in part:
                                    season = str(part["season"])
                                if "draft_status" in part:
                                    draft_status = str(part["draft_status"])
                        if league_key:
                            result.append({
                                "league_id": league_id,
                                "league_key": league_key,
                                "name": league_name,
                                "num_teams": num_teams,
                                "season": season,
                                "draft_status": draft_status,
                            })
        except Exception as exc:
            logger.warning("Direct Yahoo leagues parse incomplete: %s", exc)

        return result

    async def _fetch_teams_direct(self) -> List[Dict[str, Any]]:
        """Fetch user teams via direct Yahoo API call (bypasses yfpy model parsing)."""
        access_token = self._token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token available")

        url = (
            "https://fantasysports.yahooapis.com/fantasy/v2"
            "/users;use_login=1/games;game_keys=nfl/teams?format=json"
        )
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})

        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Yahoo token expired. Please reconnect.")
        resp.raise_for_status()

        data = resp.json()
        result: List[Dict[str, Any]] = []

        try:
            games = (
                data.get("fantasy_content", {})
                .get("users", {}).get("0", {})
                .get("user", [{}])
            )
            # user payload is a list; the last element contains games
            games_block = None
            for item in (games if isinstance(games, list) else [games]):
                if isinstance(item, dict) and "games" in item:
                    games_block = item["games"]
                    break

            if not games_block:
                return result

            # iterate game entries (keys are "0", "1", ... plus "count")
            for gkey, gval in games_block.items():
                if gkey == "count" or not isinstance(gval, dict):
                    continue
                game_list = gval.get("game", [])
                if not isinstance(game_list, list):
                    continue
                for entry in game_list:
                    if not isinstance(entry, dict) or "teams" not in entry:
                        continue
                    teams_block = entry["teams"]
                    for tkey, tval in teams_block.items():
                        if tkey == "count" or not isinstance(tval, dict):
                            continue
                        team_info_list = tval.get("team", [])
                        if not isinstance(team_info_list, list):
                            continue
                        # team data is spread across list elements
                        team_id = None
                        team_key = None
                        team_name = "Unknown Team"
                        league_key = None
                        for part in team_info_list:
                            if isinstance(part, list):
                                for sub in part:
                                    if isinstance(sub, dict):
                                        if "team_id" in sub:
                                            team_id = str(sub["team_id"])
                                        if "team_key" in sub:
                                            team_key = str(sub["team_key"])
                                        if "name" in sub:
                                            team_name = str(sub["name"])
                            elif isinstance(part, dict):
                                if "team_id" in part:
                                    team_id = str(part["team_id"])
                                if "team_key" in part:
                                    team_key = str(part["team_key"])
                                if "name" in part:
                                    team_name = str(part["name"])
                        if team_key:
                            # league_key is team_key up to the ".t." segment
                            lk_parts = team_key.rsplit(".t.", 1)
                            league_key = lk_parts[0] if len(lk_parts) == 2 else None
                        result.append({
                            "team_id": team_id,
                            "team_key": team_key,
                            "name": team_name,
                            "league_key": league_key,
                        })
        except Exception as exc:
            logger.warning("Direct Yahoo teams parse incomplete: %s", exc)

        return result

    async def get_user_teams(self) -> List[Dict[str, Any]]:
        """
        Get all teams the user owns across leagues.

        Returns:
            List of team dicts with team_id, league_id, name, etc.
        """
        cache_key = self._user_cache_key("teams")
        if cache_key in _teams_cache:
            return _teams_cache[cache_key]

        # Try yfpy first, fall back to direct API if yfpy model parsing fails.
        try:
            def _fetch():
                query = self._get_query()
                result = query.get_user_teams()
                return result, self._extract_token_from_query(query)

            loop = asyncio.get_event_loop()
            teams, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)

            result = []
            if teams:
                for team in teams:
                    team_dict = {
                        "team_id": getattr(team, "team_id", None),
                        "team_key": getattr(team, "team_key", None),
                        "name": self._extract_name(getattr(team, "name", "Unknown Team")),
                        "league_key": getattr(team, "league_key", None),
                    }
                    result.append(team_dict)

            _teams_cache[cache_key] = result
            return result
        except Exception as yfpy_err:
            logger.warning("yfpy get_user_teams failed (%s), using direct API", yfpy_err)

        # Direct Yahoo API fallback
        result = await self._fetch_teams_direct()
        _teams_cache[cache_key] = result
        return result

    async def _fetch_roster_direct(
        self, team_key: str, week: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch team roster via direct Yahoo API call (bypasses yfpy model parsing)."""
        access_token = self._token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token available")

        url = (
            f"https://fantasysports.yahooapis.com/fantasy/v2"
            f"/team/{team_key}/roster/players?format=json"
        )
        if week:
            url += f"&week={week}"

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})

        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Yahoo token expired. Please reconnect.")
        resp.raise_for_status()

        data = resp.json()
        result: List[Dict[str, Any]] = []

        try:
            roster_block = (
                data.get("fantasy_content", {})
                .get("team", [{}])
            )
            # Find the roster element in the team list
            players_block = None
            for item in (roster_block if isinstance(roster_block, list) else [roster_block]):
                if isinstance(item, dict) and "roster" in item:
                    players_container = item["roster"]
                    if isinstance(players_container, dict):
                        players_block = players_container.get("0", {}).get("players", players_container.get("players"))
                    break

            if not players_block:
                return result

            for pkey, pval in players_block.items():
                if pkey == "count" or not isinstance(pval, dict):
                    continue
                player_info_list = pval.get("player", [])
                if not isinstance(player_info_list, list):
                    continue

                player_id = None
                player_key = None
                player_name = "Unknown"
                position = None
                team = None
                status = None
                injury_status = None

                for part in player_info_list:
                    if isinstance(part, list):
                        for sub in part:
                            if isinstance(sub, dict):
                                if "player_id" in sub:
                                    player_id = str(sub["player_id"])
                                if "player_key" in sub:
                                    player_key = str(sub["player_key"])
                                if "display_position" in sub:
                                    position = str(sub["display_position"])
                                if "editorial_team_abbr" in sub:
                                    team = str(sub["editorial_team_abbr"])
                                if "status" in sub:
                                    status = str(sub["status"])
                                if "name" in sub:
                                    name_val = sub["name"]
                                    if isinstance(name_val, dict):
                                        player_name = str(name_val.get("full") or name_val.get("first") or "Unknown")
                                    else:
                                        player_name = str(name_val)
                    elif isinstance(part, dict):
                        if "player_id" in part:
                            player_id = str(part["player_id"])
                        if "player_key" in part:
                            player_key = str(part["player_key"])
                        if "display_position" in part:
                            position = str(part["display_position"])
                        if "editorial_team_abbr" in part:
                            team = str(part["editorial_team_abbr"])
                        if "status" in part:
                            status = str(part["status"])
                        if "status_full" in part:
                            injury_status = str(part["status_full"])
                        if "name" in part:
                            name_val = part["name"]
                            if isinstance(name_val, dict):
                                player_name = str(name_val.get("full") or name_val.get("first") or "Unknown")
                            else:
                                player_name = str(name_val)

                if player_key or player_id:
                    result.append({
                        "player_id": player_id,
                        "player_key": player_key,
                        "name": player_name,
                        "position": position,
                        "team": team,
                        "status": status,
                        "injury_status": injury_status,
                    })
        except Exception as exc:
            logger.warning("Direct Yahoo roster parse incomplete: %s", exc)

        return result

    async def get_team_roster(
        self, league_id: str, team_id: str, week: Optional[int] = None,
        team_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get roster for a specific team.

        Args:
            league_id: Yahoo league ID
            team_id: Yahoo team ID within the league
            week: Optional week number for historical roster
            team_key: Optional full team key (e.g. "449.l.12345.t.3") for direct API fallback

        Returns:
            List of player dicts with player_id, name, position, etc.
        """
        cache_key = self._user_cache_key("roster", league_id, team_id, week or "current")
        if cache_key in _roster_cache:
            return _roster_cache[cache_key]

        # Try yfpy first, fall back to direct API if yfpy model parsing fails.
        try:
            def _fetch():
                query = self._get_query(league_id)
                if week:
                    result = query.get_team_roster_player_info_by_week(team_id, week)
                else:
                    result = query.get_team_roster_player_stats(team_id)
                return result, self._extract_token_from_query(query)

            loop = asyncio.get_event_loop()
            roster, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)

            result = []
            if roster:
                for player in roster:
                    player_dict = {
                        "player_id": getattr(player, "player_id", None),
                        "player_key": getattr(player, "player_key", None),
                        "name": self._extract_name(getattr(player, "name", {})),
                        "position": getattr(player, "display_position", None),
                        "team": getattr(player, "editorial_team_abbr", None),
                        "status": getattr(player, "status", None),
                        "injury_status": getattr(player, "injury_status", None),
                    }
                    result.append(player_dict)

            _roster_cache[cache_key] = result
            return result
        except Exception as yfpy_err:
            if team_key:
                logger.warning("yfpy get_team_roster failed (%s), using direct API", yfpy_err)
            else:
                logger.error("Failed to fetch team roster: %s (no team_key for fallback)", yfpy_err)
                raise

        # Direct Yahoo API fallback
        result = await self._fetch_roster_direct(team_key, week)
        _roster_cache[cache_key] = result
        return result

    async def get_league_players(
        self,
        league_key: str,
        position: Optional[str] = None,
        count: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch available (free agent) players from a Yahoo league.

        Uses direct Yahoo API: /league/{key}/players;status=A;sort=AR

        Args:
            league_key: Full Yahoo league key (e.g. "449.l.12345")
            position: Optional position filter (QB, RB, WR, TE, K)
            count: Max number of players to return (default 50)

        Returns:
            List of player dicts with player_id, player_key, name, position, team,
            status, percent_owned.
        """
        cache_key = self._user_cache_key("waiver", league_key, position or "ALL", count)
        if cache_key in _waiver_cache:
            return _waiver_cache[cache_key]

        access_token = self._token_data.get("access_token")
        if not access_token:
            raise ValueError("No access token available")

        filters = f"status=A;sort=AR;count={count}"
        if position:
            filters += f";position={position}"

        url = (
            f"https://fantasysports.yahooapis.com/fantasy/v2"
            f"/league/{league_key}/players;{filters}?format=json"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})

        if resp.status_code == 401:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Yahoo token expired. Please reconnect.")
        resp.raise_for_status()

        data = resp.json()
        result: List[Dict[str, Any]] = []

        try:
            league_content = data.get("fantasy_content", {}).get("league", [])
            players_block = None
            for item in (league_content if isinstance(league_content, list) else [league_content]):
                if isinstance(item, dict) and "players" in item:
                    players_block = item["players"]
                    break

            if not players_block:
                _waiver_cache[cache_key] = result
                return result

            for pkey, pval in players_block.items():
                if pkey == "count" or not isinstance(pval, dict):
                    continue
                player_info_list = pval.get("player", [])
                if not isinstance(player_info_list, list):
                    continue

                player_id = None
                player_key_val = None
                player_name = "Unknown"
                player_position = None
                team = None
                status = None
                percent_owned = None

                for part in player_info_list:
                    if isinstance(part, list):
                        for sub in part:
                            if isinstance(sub, dict):
                                if "player_id" in sub:
                                    player_id = str(sub["player_id"])
                                if "player_key" in sub:
                                    player_key_val = str(sub["player_key"])
                                if "display_position" in sub:
                                    player_position = str(sub["display_position"])
                                if "editorial_team_abbr" in sub:
                                    team = str(sub["editorial_team_abbr"])
                                if "status" in sub:
                                    status = str(sub["status"])
                                if "name" in sub:
                                    name_val = sub["name"]
                                    if isinstance(name_val, dict):
                                        player_name = str(
                                            name_val.get("full") or name_val.get("first") or "Unknown"
                                        )
                                    else:
                                        player_name = str(name_val)
                                if "percent_owned" in sub:
                                    po = sub["percent_owned"]
                                    if isinstance(po, dict):
                                        try:
                                            percent_owned = float(po.get("value", 0))
                                        except (TypeError, ValueError):
                                            pass
                                    elif isinstance(po, list):
                                        for po_item in po:
                                            if isinstance(po_item, dict) and "value" in po_item:
                                                try:
                                                    percent_owned = float(po_item["value"])
                                                except (TypeError, ValueError):
                                                    pass
                    elif isinstance(part, dict):
                        if "player_id" in part:
                            player_id = str(part["player_id"])
                        if "player_key" in part:
                            player_key_val = str(part["player_key"])
                        if "display_position" in part:
                            player_position = str(part["display_position"])
                        if "editorial_team_abbr" in part:
                            team = str(part["editorial_team_abbr"])
                        if "status" in part:
                            status = str(part["status"])
                        if "name" in part:
                            name_val = part["name"]
                            if isinstance(name_val, dict):
                                player_name = str(
                                    name_val.get("full") or name_val.get("first") or "Unknown"
                                )
                            else:
                                player_name = str(name_val)
                        if "percent_owned" in part:
                            po = part["percent_owned"]
                            if isinstance(po, dict):
                                try:
                                    percent_owned = float(po.get("value", 0))
                                except (TypeError, ValueError):
                                    pass
                            elif isinstance(po, list):
                                for po_item in po:
                                    if isinstance(po_item, dict) and "value" in po_item:
                                        try:
                                            percent_owned = float(po_item["value"])
                                        except (TypeError, ValueError):
                                            pass

                if player_key_val or player_id:
                    result.append({
                        "player_id": player_id,
                        "player_key": player_key_val,
                        "name": player_name,
                        "position": player_position,
                        "team": team,
                        "status": status,
                        "percent_owned": percent_owned,
                    })

        except Exception as exc:
            logger.warning("Direct Yahoo league players parse incomplete: %s", exc)

        _waiver_cache[cache_key] = result
        return result

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
            result = query.get_league_draft_results()
            return result, self._extract_token_from_query(query)

        loop = asyncio.get_event_loop()
        try:
            draft_results, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)
            
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
            result = query.get_player_stats_for_season(player_key)
            return result, self._extract_token_from_query(query)

        loop = asyncio.get_event_loop()
        try:
            player, token_update = await loop.run_in_executor(_executor, _fetch)
            self._merge_token_update(token_update)
            
            if not player:
                return None
            
            return {
                "player_id": getattr(player, "player_id", None),
                "player_key": getattr(player, "player_key", None),
                "name": self._extract_name(getattr(player, "name", {})),
                "position": getattr(player, "display_position", None),
                "team": getattr(player, "editorial_team_abbr", None),
                "percent_owned": getattr(player, "percent_owned", {}).get("value", 0),
            }
        except Exception as e:
            logger.error(f"Failed to fetch player details: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear all in-memory Yahoo cache entries for this user."""
        user_prefix = f"{self._user_id}:"

        for cache in (_leagues_cache, _teams_cache, _roster_cache, _waiver_cache):
            for key in list(cache.keys()):
                if str(key).startswith(user_prefix):
                    del cache[key]

        logger.info("Yahoo Fantasy cache cleared for user_id=%s", self._user_id)


def get_yahoo_service(token_data: Dict[str, Any], user_id: str) -> YahooFantasyService:
    """Create a Yahoo service bound to user token data."""
    return YahooFantasyService(token_data=token_data, user_id=user_id)
