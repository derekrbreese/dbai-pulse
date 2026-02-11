"""
SQLite persistence service for Yahoo auth and team feedback data.
"""

import json
import logging
import sqlite3
import threading
import time
from typing import Any, Dict, Optional

from config import get_settings

logger = logging.getLogger(__name__)


class SQLiteStorage:
    """Repository-style storage wrapper for local SQLite persistence."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db_path = self.settings.sqlite_db_absolute_path
        self._write_lock = threading.Lock()

    def initialize(self) -> None:
        """Create required tables if they do not already exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS yahoo_tokens (
                    user_id TEXT PRIMARY KEY,
                    encrypted_token_json TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_login_at INTEGER
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_feedback_preferences (
                    user_id TEXT NOT NULL,
                    team_key TEXT NOT NULL,
                    scoring TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    focus TEXT NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, team_key)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_insights_cache (
                    user_id TEXT NOT NULL,
                    team_key TEXT NOT NULL,
                    prefs_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, team_key, prefs_key)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS yahoo_sleeper_player_map (
                    user_id TEXT NOT NULL,
                    team_key TEXT NOT NULL,
                    yahoo_identity TEXT NOT NULL,
                    yahoo_player_key TEXT,
                    yahoo_player_id TEXT,
                    sleeper_id TEXT NOT NULL,
                    confidence REAL,
                    match_reason TEXT,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, team_key, yahoo_identity)
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_yahoo_sleeper_player_map_player_id
                ON yahoo_sleeper_player_map (user_id, team_key, yahoo_player_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        """Open a sqlite connection with row dictionaries enabled."""
        connection = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Load one user row by email."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, password_hash, created_at, updated_at, last_login_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load one user row by primary id."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, password_hash, created_at, updated_at, last_login_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        return dict(row) if row else None

    def create_user(self, user_id: str, email: str, password_hash: str) -> Dict[str, Any]:
        """Create one user row and return persisted values."""
        now = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, created_at, updated_at, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, email, password_hash, now, now, now),
                )

        return {
            "id": user_id,
            "email": email,
            "password_hash": password_hash,
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
        }

    def update_user_last_login(self, user_id: str) -> int:
        """Update last_login_at and return timestamp."""
        now = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET last_login_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, user_id),
                )

        return now

    def get_yahoo_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Load encrypted Yahoo token record for a user."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, encrypted_token_json, expires_at, created_at, updated_at
                FROM yahoo_tokens
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return dict(row)

    def save_yahoo_token(self, user_id: str, encrypted_token_json: str, expires_at: int) -> None:
        """Insert or update encrypted Yahoo token for a user."""
        now = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO yahoo_tokens (user_id, encrypted_token_json, expires_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        encrypted_token_json = excluded.encrypted_token_json,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, encrypted_token_json, expires_at, now, now),
                )

    def delete_yahoo_token(self, user_id: str) -> None:
        """Delete Yahoo token row for a user."""
        with self._write_lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM yahoo_tokens WHERE user_id = ?", (user_id,))

    def get_team_preferences(self, user_id: str, team_key: str) -> Optional[Dict[str, Any]]:
        """Load saved team preferences for one user/team pair."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, team_key, scoring, risk, focus, updated_at
                FROM team_feedback_preferences
                WHERE user_id = ? AND team_key = ?
                """,
                (user_id, team_key),
            ).fetchone()

        return dict(row) if row else None

    def save_team_preferences(
        self,
        user_id: str,
        team_key: str,
        scoring: str,
        risk: str,
        focus: str,
    ) -> int:
        """Persist team preferences and return updated unix timestamp."""
        updated_at = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO team_feedback_preferences (user_id, team_key, scoring, risk, focus, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, team_key) DO UPDATE SET
                        scoring = excluded.scoring,
                        risk = excluded.risk,
                        focus = excluded.focus,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, team_key, scoring, risk, focus, updated_at),
                )

        return updated_at

    def get_team_insights_cache(
        self, user_id: str, team_key: str, prefs_key: str
    ) -> Optional[Dict[str, Any]]:
        """Return cached insights payload when it is still valid."""
        now = int(time.time())

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json, expires_at
                FROM team_insights_cache
                WHERE user_id = ? AND team_key = ? AND prefs_key = ?
                """,
                (user_id, team_key, prefs_key),
            ).fetchone()

        if row is None:
            return None

        expires_at = int(row["expires_at"])
        if expires_at <= now:
            self.clear_team_insights_cache(user_id, team_key, prefs_key)
            return None

        try:
            return json.loads(row["payload_json"])
        except json.JSONDecodeError:
            logger.warning("Failed to decode cached insights payload for %s/%s", user_id, team_key)
            self.clear_team_insights_cache(user_id, team_key, prefs_key)
            return None

    def save_team_insights_cache(
        self,
        user_id: str,
        team_key: str,
        prefs_key: str,
        payload: Dict[str, Any],
        ttl_seconds: int,
    ) -> int:
        """Store insights payload and return cache expiry timestamp."""
        now = int(time.time())
        expires_at = now + ttl_seconds
        payload_json = json.dumps(payload)

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO team_insights_cache (
                        user_id, team_key, prefs_key, payload_json, expires_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, team_key, prefs_key) DO UPDATE SET
                        payload_json = excluded.payload_json,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, team_key, prefs_key, payload_json, expires_at, now),
                )

        return expires_at

    def clear_team_insights_cache(
        self,
        user_id: str,
        team_key: Optional[str] = None,
        prefs_key: Optional[str] = None,
    ) -> None:
        """Clear cached insights rows for a user, optionally narrowed to team/preferences."""
        query = "DELETE FROM team_insights_cache WHERE user_id = ?"
        params: list[Any] = [user_id]

        if team_key is not None:
            query += " AND team_key = ?"
            params.append(team_key)

        if prefs_key is not None:
            query += " AND prefs_key = ?"
            params.append(prefs_key)

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(query, tuple(params))

    @staticmethod
    def _mapping_identities(
        yahoo_player_key: Optional[str],
        yahoo_player_id: Optional[str],
    ) -> list[str]:
        """Build lookup identities for Yahoo player mapping records."""
        identities: list[str] = []
        clean_player_key = str(yahoo_player_key or "").strip()
        clean_player_id = str(yahoo_player_id or "").strip()

        if clean_player_key:
            identities.append(f"key:{clean_player_key}")
        if clean_player_id:
            identities.append(f"id:{clean_player_id}")

        return identities

    def get_saved_player_mapping(
        self,
        user_id: str,
        team_key: str,
        yahoo_player_key: Optional[str],
        yahoo_player_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Load a previously saved Yahoo-to-Sleeper mapping for a player identity."""
        identities = self._mapping_identities(yahoo_player_key, yahoo_player_id)
        if not identities:
            return None

        placeholders = ",".join("?" for _ in identities)
        query = f"""
            SELECT
                user_id,
                team_key,
                yahoo_identity,
                yahoo_player_key,
                yahoo_player_id,
                sleeper_id,
                confidence,
                match_reason,
                updated_at
            FROM yahoo_sleeper_player_map
            WHERE user_id = ? AND team_key = ? AND yahoo_identity IN ({placeholders})
            ORDER BY updated_at DESC
        """

        params = [user_id, team_key, *identities]
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        if not rows:
            return None

        by_identity: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            row_dict = dict(row)
            identity = row_dict.get("yahoo_identity")
            if identity and identity not in by_identity:
                by_identity[identity] = row_dict

        for identity in identities:
            if identity in by_identity:
                return by_identity[identity]

        return dict(rows[0])

    def save_player_mapping(
        self,
        user_id: str,
        team_key: str,
        yahoo_player_key: Optional[str],
        yahoo_player_id: Optional[str],
        sleeper_id: str,
        confidence: Optional[float],
        match_reason: str,
    ) -> int:
        """Persist Yahoo-to-Sleeper mapping identities and return updated timestamp."""
        identities = self._mapping_identities(yahoo_player_key, yahoo_player_id)
        normalized_sleeper_id = str(sleeper_id or "").strip()
        if not identities or not normalized_sleeper_id:
            return int(time.time())

        updated_at = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                for identity in identities:
                    conn.execute(
                        """
                        INSERT INTO yahoo_sleeper_player_map (
                            user_id,
                            team_key,
                            yahoo_identity,
                            yahoo_player_key,
                            yahoo_player_id,
                            sleeper_id,
                            confidence,
                            match_reason,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, team_key, yahoo_identity) DO UPDATE SET
                            yahoo_player_key = excluded.yahoo_player_key,
                            yahoo_player_id = excluded.yahoo_player_id,
                            sleeper_id = excluded.sleeper_id,
                            confidence = excluded.confidence,
                            match_reason = excluded.match_reason,
                            updated_at = excluded.updated_at
                        """,
                        (
                            user_id,
                            team_key,
                            identity,
                            str(yahoo_player_key or "").strip() or None,
                            str(yahoo_player_id or "").strip() or None,
                            normalized_sleeper_id,
                            confidence,
                            match_reason,
                            updated_at,
                        ),
                    )

        return updated_at

    def get_app_setting(self, key: str) -> Optional[Dict[str, Any]]:
        """Get one app-level setting row."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT key, value, updated_at
                FROM app_settings
                WHERE key = ?
                """,
                (key,),
            ).fetchone()

        return dict(row) if row else None

    def save_app_setting(self, key: str, value: str) -> int:
        """Set app-level setting value and return updated timestamp."""
        updated_at = int(time.time())

        with self._write_lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, updated_at),
                )

        return updated_at


_storage: Optional[SQLiteStorage] = None


def get_storage() -> SQLiteStorage:
    """Get or create the singleton storage service."""
    global _storage
    if _storage is None:
        _storage = SQLiteStorage()
    return _storage
