# Phase 4: The Pulse - Implementation Plan

## Overview
"What's the Pulse?" - The differentiator feature that synthesizes expert opinions, Reddit sentiment, and Sleeper data to provide actionable fantasy football insights using **Gemini 3.0 Flash**.

---

## Architecture

### Data Flow
```
Player Selection
    ↓
[Parallel Fetching]
    ├─ Sleeper API → Projections + Recent Stats
    ├─ YouTube API → Fantasy Podcast Transcripts
    └─ Reddit API → r/fantasyfootball Posts & Comments
    ↓
Gemini 3.0 Flash Synthesis
    ↓
Conviction Score + Recommendation
    ↓
Display in UI
```

---

## Backend Components

### 1. YouTube Transcript Service
**File:** `backend/services/youtube.py`

**Purpose:** Fetch and process YouTube video transcripts from fantasy football experts.

**Key Functions:**
- `search_player_videos(player_name, limit=5)` - Search YouTube for recent player analysis
- `get_transcript(video_id)` - Fetch transcript using youtube-transcript-api
- `extract_player_mentions(transcript, player_name)` - Get relevant segments

**Data Sources:**
- Fantasy Footballers podcast
- Late Round Podcast
- FantasyPros videos
- CBS Sports Fantasy

**Implementation Notes:**
- Use `youtube-transcript-api` library (no API key needed for transcripts)
- Cache transcripts for 6 hours (`transcript_cache_ttl`)
- Focus on videos from last 7 days

---

### 2. Reddit Sentiment Service
**File:** `backend/services/reddit.py`

**Purpose:** Analyze Reddit discussions for player sentiment.

**Key Functions:**
- `search_player_posts(player_name, limit=10)` - Search r/fantasyfootball
- `analyze_sentiment(posts)` - Score sentiment (-1 to +1)
- `extract_injury_mentions(posts)` - Flag injury concerns
- `calculate_hype_score(posts)` - Measure excitement level

**Metrics:**
- Sentiment score: -1 (sell) to +1 (buy)
- Posts analyzed count
- Comments analyzed count
- Injury mention frequency
- Hype score: 0-10

**Implementation Notes:**
- Use `praw` (Python Reddit API Wrapper)
- Requires Reddit API credentials in `.env`
- Focus on last 48 hours of posts
- Cache for 30 minutes

---

### 3. Gemini Synthesis Service
**File:** `backend/services/gemini_synthesis.py`

**Purpose:** Use Gemini 3.0 Flash to synthesize all data sources into actionable insights.

**Key Functions:**
- `synthesize_expert_takes(transcripts, player_name)` - Analyze YouTube content
- `generate_pulse_summary(player_data, expert_takes, reddit_sentiment)` - Create final recommendation
- `calculate_conviction_score(data)` - Score confidence (HIGH, MEDIUM-HIGH, MIXED, MEDIUM-LOW, LOW)

**Gemini Model:** `gemini-3.0-flash`

**Prompt Template:**
```
You are an expert fantasy football analyst. Analyze the following data for {player_name}:

PROJECTIONS:
- Sleeper Projection: {projection} pts
- L3W Average: {l3w_avg} pts
- Trend: {trend}
- Flags: {flags}

EXPERT TAKES (from YouTube):
{youtube_summaries}

REDDIT SENTIMENT:
- Sentiment Score: {sentiment_score}
- Posts Analyzed: {post_count}
- Key Themes: {themes}

Provide:
1. START/SIT recommendation for this week
2. Conviction level (HIGH, MEDIUM-HIGH, MIXED, MEDIUM-LOW, LOW)
3. 2-3 sentence reasoning
4. Key risk factors
```

**Output Schema:**
```python
{
    "recommendation": "START" | "SIT" | "FLEX",
    "conviction": "HIGH" | "MEDIUM-HIGH" | "MIXED" | "MEDIUM-LOW" | "LOW",
    "reasoning": str,
    "risk_factors": List[str],
    "expert_consensus": str,
    "sentiment_summary": str
}
```

---

### 4. API Endpoint Updates
**File:** `backend/routers/players.py`

**New Endpoint:**
```python
@router.get("/{sleeper_id}/pulse", response_model=PulseResult)
async def get_player_pulse(sleeper_id: str):
    """
    Get full 'Pulse' analysis combining:
    - Sleeper projections & stats
    - YouTube expert takes
    - Reddit sentiment
    - Gemini synthesis
    """
```

**Response Model (`models/schemas.py`):**
```python
class PulseResult(BaseModel):
    player: EnhancedPlayer
    expert_takes: List[ExpertTake]
    reddit_sentiment: Optional[RedditSentiment]
    gemini_analysis: GeminiAnalysis
    conviction: str  # "HIGH", "MEDIUM-HIGH", "MIXED", "MEDIUM-LOW", "LOW"
    final_recommendation: str  # "START", "SIT", "FLEX"
```

---

## Frontend Components

### 1. Pulse Button
**File:** `frontend/src/components/PulseButton.jsx`

**Purpose:** Trigger full Pulse analysis.

**UI:**
```
┌──────────────────────────────┐
│  🔮 What's the Pulse?        │
│  [Button with gradient]      │
└──────────────────────────────┘
```

**States:**
- Idle: Gradient button
- Loading: Spinner + "Analyzing..."
- Done: Shows PulseModal

---

### 2. Pulse Modal
**File:** `frontend/src/components/PulseModal.jsx`

**Purpose:** Display comprehensive Pulse analysis.

**Sections:**
1. **Header**: Player name + conviction badge
2. **Recommendation**: START/SIT/FLEX with reasoning
3. **Expert Takes**: Collapsible list from YouTube
4. **Reddit Buzz**: Sentiment + top comments
5. **Risk Factors**: Warning badges

**Design:**
- Full-screen modal with glassmorphism
- Animated entrance (scale + fade)
- Color-coded conviction badges
- Expandable sections

---

## Dependencies

### Python Packages
```txt
# Add to requirements.txt
google-generativeai==0.3.2  # Gemini 3.0 Flash
youtube-transcript-api==0.6.1
praw==7.7.1  # Reddit API
```

### Environment Variables
```
GEMINI_API_KEY=your_gemini_api_key  # ✅ Already set
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USERNAME=your_reddit_username
```

---

## Implementation Phases

### Phase 4.1: YouTube + Gemini (MVP)
- [/] YouTube transcript fetching
- [/] Gemini 3.0 Flash integration
- [/] Basic synthesis endpoint
- [/] Pulse button UI
- [/] Results display

### Phase 4.2: Reddit Integration
- [ ] Reddit API setup
- [ ] Sentiment analysis
- [ ] Hype score calculation
- [ ] Add to Pulse results

### Phase 4.3: Polish
- [ ] Caching optimization
- [ ] Error handling
- [ ] Loading states
- [ ] Animation polish

---

## Success Metrics

**Technical:**
- Gemini API response < 3 seconds
- YouTube transcript fetch < 2 seconds
- Reddit search < 1 second
- Total Pulse load < 6 seconds

**User Experience:**
- Clear START/SIT recommendation
- Conviction score is accurate
- Expert takes add value
- UI feels premium

---

## Risk Mitigation

**API Rate Limits:**
- Cache aggressively (transcripts: 6hr, Reddit: 30min)
- Implement backoff strategy
- Graceful degradation if APIs fail

**Gemini Token Limits:**
- Summarize YouTube transcripts before sending
- Use flash model (cheaper, faster)
- Estimate: ~100-200 tokens per request

**Data Quality:**
- Validate transcript relevance
- Filter out generic Reddit posts
- Verify expert source credibility

---

## Next Steps

1. Install dependencies (`pip install google-generativeai youtube-transcript-api praw`)
2. Implement `backend/services/youtube.py`
3. Implement `backend/services/gemini_synthesis.py`
4. Add `/pulse` endpoint
5. Create Pulse button component
6. Test with sample players
