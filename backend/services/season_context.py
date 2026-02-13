"""Shared helper for resolving the current NFL season context."""

from typing import Tuple

from config import get_settings
from services.sleeper import get_sleeper_client


async def resolve_season_context() -> Tuple[int, int, str]:
    """Return (season, week, season_type) from Sleeper's NFL state."""
    settings = get_settings()
    client = get_sleeper_client()
    return await client.get_current_season_context(
        settings.nfl_season, settings.nfl_week
    )
