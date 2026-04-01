"""
Pydantic models for dbAI Pulse API.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PlayerBase(BaseModel):
    """Base player information from Sleeper."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None
    bye_week: Optional[int] = None
    espn_id: Optional[str] = None
    injury_status: Optional[str] = None


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
    trend_delta: Optional[float] = None  # latest week vs avg, e.g. +3.2
    weekly_points: List[float] = []
    volatility_score: Optional[float] = None  # coefficient of variation, 0.0-1.0
    ceiling_value: Optional[float] = None  # best week score
    floor_value: Optional[float] = None  # worst week score


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
    ecr_rank: Optional[int] = None  # FantasyPros ECR overall rank
    ecr_best: Optional[int] = None  # Best expert rank
    ecr_worst: Optional[int] = None  # Worst expert rank


class PulseResult(BaseModel):
    """Full 'What's the Pulse?' result."""

    player: EnhancedPlayer
    gemini_analysis: GeminiAnalysis
    youtube_context: str = ""
    expert_takes: List[ExpertTake] = []
    reddit_sentiment: Optional[RedditSentiment] = None
    season: Optional[int] = None
    week: Optional[int] = None
    season_type: Optional[str] = None


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
    season: Optional[int] = None
    week: Optional[int] = None
    season_type: Optional[str] = None


class PlayerSearchResult(BaseModel):
    """Search result for player lookup."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None
    espn_id: Optional[str] = None


class NearMatchCandidate(BaseModel):
    """A near-miss Sleeper player suggestion for an unmatched Yahoo player."""

    sleeper_id: str
    name: str
    position: str
    team: Optional[str] = None
    similarity: float


class ManualMatchRequest(BaseModel):
    """Request body for manual Yahoo-to-Sleeper player matching."""

    yahoo_player_key: str
    yahoo_player_id: Optional[str] = None
    sleeper_id: str


class ManualUnmatchRequest(BaseModel):
    """Request body for unlinking a Yahoo-to-Sleeper match."""

    yahoo_player_key: str
    yahoo_player_id: Optional[str] = None


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


class YahooTeamSummary(BaseModel):
    """Basic Yahoo team summary metadata."""

    team_key: str
    team_name: str
    league_key: str
    league_name: Optional[str] = None
    season: Optional[int] = None


class TeamFeedbackPreferences(BaseModel):
    """Saved feedback customization preferences for one team."""

    scoring: Literal["ppr", "half_ppr", "std"] = "ppr"
    risk: Literal["conservative", "balanced", "aggressive"] = "balanced"
    focus: Literal["floor", "upside", "ceiling"] = "upside"
    updated_at: Optional[int] = None


class TeamFeedbackPreferencesUpdate(BaseModel):
    """Request model for team preference updates."""

    scoring: Literal["ppr", "half_ppr", "std"] = "ppr"
    risk: Literal["conservative", "balanced", "aggressive"] = "balanced"
    focus: Literal["floor", "upside", "ceiling"] = "upside"


class FeedbackScoreBreakdown(BaseModel):
    """Decomposed score showing how each factor contributed."""

    base: float  # raw projection score
    recent_adj: float = 0.0  # L3W performance adjustment
    flag_bonus: float = 0.0  # performance flag bonuses
    risk_adj: float = 0.0  # risk preference adjustment
    focus_adj: float = 0.0  # focus preference adjustment
    injury_penalty: float = 0.0  # injury status deduction
    final: float  # final composite score


class RosterInsightPlayer(BaseModel):
    """Roster player row including Yahoo-to-Sleeper matching and feedback."""

    yahoo_player_key: str
    name: str
    position: Optional[str] = None
    team: Optional[str] = None
    status: Optional[str] = None
    injury_status: Optional[str] = None
    matched_sleeper_id: Optional[str] = None
    match_confidence: Optional[float] = None
    match_reason: str
    enhanced_player: Optional[EnhancedPlayer] = None
    custom_feedback: str
    feedback_score: Optional[float] = None
    score_breakdown: Optional[FeedbackScoreBreakdown] = None
    near_matches: List[NearMatchCandidate] = Field(default_factory=list)


class RosterInsightsResponse(BaseModel):
    """Full roster insights payload for a Yahoo team import."""

    team: YahooTeamSummary
    preferences: TeamFeedbackPreferences
    players: List[RosterInsightPlayer] = Field(default_factory=list)
    matched_count: int
    unmatched_count: int
    summary: str
    cached: bool = False
    imported_at: int


class WaiverPlayerInsight(BaseModel):
    """Single player row in waiver wire results."""

    yahoo_player_key: str
    name: str
    position: Optional[str] = None
    team: Optional[str] = None
    percent_owned: Optional[float] = None
    matched_sleeper_id: Optional[str] = None
    enhanced_player: Optional[EnhancedPlayer] = None
    recommendation: str  # "GRAB", "WATCH", "SKIP"
    reasoning: str
    score: Optional[float] = None
    score_breakdown: Optional[FeedbackScoreBreakdown] = None


class WaiverWireResponse(BaseModel):
    """Full waiver wire intelligence payload."""

    league_key: str
    league_name: Optional[str] = None
    preferences: TeamFeedbackPreferences
    players: List[WaiverPlayerInsight] = Field(default_factory=list)
    matched_count: int
    total_scanned: int
    position_filter: Optional[str] = None
    summary: str
    cached: bool = False
    generated_at: int


class CalibrationConvictionStats(BaseModel):
    """Accuracy stats for a single conviction level."""

    total: int
    correct: int
    incorrect: int
    neutral: int
    accuracy: Optional[float] = None


class CalibrationStats(BaseModel):
    """Full calibration summary response."""

    total_resolved: int
    overall_accuracy: Optional[float] = None
    by_conviction: dict = {}
    by_recommendation: dict = {}


class AuthUser(BaseModel):
    """Authenticated application user."""

    id: str
    email: str
    created_at: int
    last_login_at: Optional[int] = None


class AuthRegisterRequest(BaseModel):
    """Registration payload for local account auth."""

    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


class AuthLoginRequest(BaseModel):
    """Login payload for local account auth."""

    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class AuthSessionResponse(BaseModel):
    """Session status response."""

    authenticated: bool
    user: Optional[AuthUser] = None


class ForgotPasswordRequest(BaseModel):
    """Forgot password payload."""

    email: str = Field(..., min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    """Reset password with token payload."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Change password (logged in) payload."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
