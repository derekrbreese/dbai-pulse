"""
Configuration and environment settings for dbAI Pulse.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    gemini_api_key: str = ""
    youtube_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""

    # Cache TTLs (in seconds)
    transcript_cache_ttl: int = 6 * 60 * 60  # 6 hours
    extraction_cache_ttl: int = 2 * 60 * 60  # 2 hours
    sleeper_cache_ttl: int = 5 * 60  # 5 minutes

    # Sleeper API
    sleeper_base_url: str = "https://api.sleeper.app/v1"

    # Current NFL season/week
    # Update these values as the season progresses
    nfl_season: int = 2025  # Current NFL season
    nfl_week: int = 16  # Default week for offseason

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
