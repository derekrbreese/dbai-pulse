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
    draft_value: Optional["DraftValue"] = None


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


class GeminiAnalysis(BaseModel):
    """Gemini AI synthesis result."""

    recommendation: str  # "START", "SIT", "FLEX"
    conviction: str  # "HIGH", "MEDIUM-HIGH", "MIXED", "MEDIUM-LOW", "LOW"
    reasoning: str
    key_factors: List[str] = []
    risk_level: str  # "LOW", "MODERATE", "HIGH"
    expert_consensus: str
    sources_used: List[str] = []  # Sources from Google Search grounding


class PulseResult(BaseModel):
    """Full 'What's the Pulse?' result."""

    player: EnhancedPlayer
    gemini_analysis: GeminiAnalysis
    youtube_context: str = ""
    expert_takes: List[ExpertTake] = []
    reddit_sentiment: Optional[RedditSentiment] = None


class ComparisonResult(BaseModel):
    """Head-to-head player comparison result."""

    player_a: EnhancedPlayer
    player_b: EnhancedPlayer
    winner: str  # "A" | "B" | "TOSS_UP"
    winner_name: str
    conviction: str  # "HIGH" | "MEDIUM" | "LOW"
    reasoning: str
    key_advantages_a: List[str] = []
    key_advantages_b: List[str] = []
    matchup_edge: str = ""
    sources_used: List[str] = []


class PlayerSearchResult(BaseModel):
    """Search result for player lookup."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None


class PlayerADP(BaseModel):
    """ADP data for a player."""

    name: str
    position: str
    adp: float
    adp_round: Optional[float] = None
    std_dev: Optional[float] = None
    high: Optional[int] = None
    low: Optional[int] = None
    times_drafted: Optional[int] = None


class PlayerADPResponse(BaseModel):
    """Response for player ADP lookup."""

    player_name: str
    adp_data: Optional[PlayerADP] = None
    scoring: str
    teams: int
    year: int


class DraftValue(BaseModel):
    """Draft value metrics for a player."""

    adp: Optional[float] = None
    adp_round: Optional[int] = None
    position_rank: Optional[int] = None
    value_tier: Optional[str] = None
    draft_flags: List[str] = []
    std_dev: Optional[float] = None
    draft_range: Optional[str] = None
