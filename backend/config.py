"""
Configuration and environment settings for dbAI Pulse.
"""

from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    gemini_api_key: str = ""
    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""

    # Yahoo Fantasy API (OAuth 2.0)
    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = ""
    yahoo_scope: str = "fspt-r"

    # Cache TTLs (in seconds)
    transcript_cache_ttl: int = 6 * 60 * 60  # 6 hours
    extraction_cache_ttl: int = 2 * 60 * 60  # 2 hours
    sleeper_cache_ttl: int = 5 * 60  # 5 minutes
    adp_cache_ttl: int = 6 * 60 * 60  # 6 hours
    yahoo_cache_ttl_seconds: int = 5 * 60  # 5 minutes

    # Email (Resend)
    resend_api_key: str = ""
    password_reset_from_email: str = "noreply@dbaifantasy.com"

    # Session + local storage
    session_secret_key: str = "change-me-session-secret"
    token_encryption_key: str = ""
    sqlite_db_path: str = "data/app.db"
    frontend_origins: str = "http://localhost:5173,http://localhost:5175,http://localhost:3000"

    # Sleeper API
    sleeper_base_url: str = "https://api.sleeper.app/v1"

    # Current NFL season/week
    # Update these values as the season progresses
    nfl_season: int = 2025  # Current NFL season
    nfl_week: int = 16  # Default week for offseason

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def frontend_origin_list(self) -> List[str]:
        """Return allowed frontend origins as a cleaned list."""
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def sqlite_db_absolute_path(self) -> Path:
        """Return absolute path to the configured SQLite database file."""
        base_dir = Path(__file__).resolve().parent
        return (base_dir / self.sqlite_db_path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
