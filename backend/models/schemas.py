"""
Pydantic models for dbAI Pulse API.
"""

from typing import List, Optional
from pydantic import BaseModel


class PlayerBase(BaseModel):
    """Base player information from Sleeper."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None
    bye_week: Optional[int] = None


class PlayerProjection(BaseModel):
    """Weekly projection data."""

    sleeper_projection: float
    adjusted_projection: Optional[float] = None


class RecentPerformance(BaseModel):
    """Recent performance metrics."""

    weeks_analyzed: int
    avg_points: float
    total_points: float
    trend: str  # "improving", "declining", "stable"
    weekly_points: List[float] = []


class EnhancedPlayer(BaseModel):
    """Full enhanced player data."""

    player: PlayerBase
    projection: PlayerProjection
    recent_performance: Optional[RecentPerformance] = None
    performance_flags: List[str] = []
    context_message: str = ""
    on_bye: bool = False


class ExpertTake(BaseModel):
    """Expert take extracted from transcript."""

    source: str
    recommendation: Optional[str] = None  # "START", "SIT", None
    reasoning: Optional[str] = None
    confidence: Optional[str] = None
    mentioned: bool = True


class RedditSentiment(BaseModel):
    """Reddit sentiment analysis result."""

    sentiment_score: float  # -1 to +1
    consensus: str  # "START", "SIT", "MIXED"
    posts_analyzed: int
    comments_analyzed: int
    injury_mentions: int
    hype_score: float
    top_comments: List[dict] = []


class PulseResult(BaseModel):
    """Full 'What's the Pulse?' result."""

    player: EnhancedPlayer
    expert_takes: List[ExpertTake] = []
    reddit_sentiment: Optional[RedditSentiment] = None
    conviction: str  # "HIGH", "MEDIUM-HIGH", "MIXED", "MEDIUM-LOW", "LOW"
    conviction_reasoning: str = ""


class PlayerSearchResult(BaseModel):
    """Search result for player lookup."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None
