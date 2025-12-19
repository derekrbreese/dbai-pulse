# Fantasy Pulse - Implementation Plan v3

> **Creative data sourcing strategy: YouTube + Podcasts + LLM synthesis**

---

## The Expert Problem: SOLVED

Instead of scraping paywalled sites, we extract expert takes from **freely available YouTube transcripts and podcast transcripts**, then use an LLM to synthesize player-specific insights.

### Why This Works

| Source | Access | Quality |
|--------|--------|---------|
| **YouTube Transcripts** | Free via `youtube-transcript-api`, no auth | High — same experts as articles |
| **Podcast Transcripts** | Many podcasts provide free transcripts | High — detailed discussions |
| **LLM Synthesis** | Feed transcript + player name → extract take | Structured output |

### Target Channels/Podcasts

| Source | Type | Content |
|--------|------|---------|
| FantasyPros | YouTube | Weekly start/sit videos |
| The Fantasy Footballers | YouTube + Podcast | Daily analysis, transcripts available |
| Fantasy Headliners | YouTube | Position-specific breakdowns |
| CBS Fantasy Football | YouTube | Weekly rankings discussions |
| The Ringer Fantasy Show | Podcast | Transcripts via Podscripts |

---

## Architecture (Revised)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FANTASY PULSE FRONTEND                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                                  │
├─────────────────────────────────────────────────────────────────────┤
│  GET  /players/{id}/pulse     Full "What's the Pulse?" synthesis    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA SERVICES                                   │
├─────────────────────────────────────────────────────────────────────┤
│  SleeperService         Stats, projections, ownership               │
│  EnhancementEngine      Flags, adjusted projections                 │
│  RedditPulse            Sentiment from r/fantasyfootball            │
│  TranscriptService      YouTube + podcast transcript fetching       │
│  ExpertSynthesizer      LLM extracts player takes from transcripts  │
│  ConvictionCalculator   Combines all signals                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## TranscriptService Design

```python
from youtube_transcript_api import YouTubeTranscriptApi

# No API key needed!
# Pull transcripts from recent start/sit videos

EXPERT_CHANNELS = {
    "FantasyPros": "UCmw_U9uM0a8zELRh0s_yb5w",
    "Fantasy Footballers": "UCH8yH8GEXS11XcpWV1Rgqnw",
    "Fantasy Headliners": "UCz...",  # Add channel IDs
}

async def get_recent_transcripts(channel_id: str, max_videos: int = 3) -> List[str]:
    """Fetch transcripts from recent videos on a channel."""
    # 1. Use YouTube Data API to get recent video IDs (or scrape search)
    # 2. Pull transcripts via youtube_transcript_api
    # 3. Return list of transcript texts
    pass

async def get_transcript(video_id: str) -> str:
    """Get transcript for a single video."""
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    return " ".join([entry["text"] for entry in transcript])
```

---

## ExpertSynthesizer: LLM-Powered Extraction

```python
import google.generativeai as genai

EXTRACTION_PROMPT = """
You are analyzing a fantasy football video/podcast transcript.
Extract the expert's take on the following player: {player_name}

From the transcript, identify:
1. START/SIT recommendation (if mentioned)
2. Key reasoning (injuries, matchup, usage trends)
3. Confidence level (must-start, safe floor, risky ceiling, etc.)
4. Any concerns or caveats mentioned

If the player is not mentioned, return: {"mentioned": false}

Transcript:
{transcript_text}

Return JSON only:
"""

async def extract_player_take(player_name: str, transcript: str) -> dict:
    """Use Gemini to extract player-specific expert take from transcript."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = EXTRACTION_PROMPT.format(
        player_name=player_name,
        transcript_text=transcript[:15000]  # Stay within context
    )
    response = model.generate_content(prompt)
    return json.loads(response.text)
```

---

## "What's the Pulse?" Panel (Updated)

```
┌──────────────────────────────────────────────────────────────────┐
│  📣 WHAT'S THE PULSE?                          [Rico Dowdle, RB] │
├──────────────────────────────────────────────────────────────────┤
│  🎯 EXPERT TAKES (from YouTube/Podcasts)                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                        │
│  FantasyPros: "START — bell cow role, 18+ touches"               │
│  Fantasy Footballers: "Smash play this week"                     │
│  Sources: 2 of 3 videos mention this player                      │
├──────────────────────────────────────────────────────────────────┤
│  🔥 REDDIT PULSE                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                        │
│  Sentiment: +0.72  [████████████░░] Unusually Bullish            │
│  "Easily Dowdle ROS" — r/fantasyfootball (+127)                  │
│  ⚠️ 2 injury mentions (minor)                                     │
├──────────────────────────────────────────────────────────────────┤
│  📊 DATA SIGNALS                                                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                        │
│  Flags: BREAKOUT_CANDIDATE, TRENDING_UP                          │
│  L3W: 18.5 pts/game (proj: 4.0)                                  │
│  Ownership: 67% (+12% this week)                                 │
├──────────────────────────────────────────────────────────────────┤
│  ✅ CONVICTION: HIGH                                              │
│  Experts, Reddit, and data all aligned.                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Conviction Scoring (v3)

```python
def calculate_conviction(
    expert_takes: List[dict],
    reddit_sentiment: float,
    flags: List[str]
) -> str:
    score = 0
    
    # Expert consensus
    start_count = sum(1 for t in expert_takes if t.get("recommendation") == "START")
    sit_count = sum(1 for t in expert_takes if t.get("recommendation") == "SIT")
    if start_count >= 2:
        score += 2
    elif sit_count >= 2:
        score -= 2
    elif start_count > sit_count:
        score += 1
    elif sit_count > start_count:
        score -= 1
    
    # Reddit signal
    if reddit_sentiment > 0.3:
        score += 1
    elif reddit_sentiment < -0.3:
        score -= 1
    
    # Data signals
    if "BREAKOUT_CANDIDATE" in flags:
        score += 1
    if "DECLINING_ROLE" in flags:
        score -= 1
    
    # Alignment bonus
    all_positive = start_count >= 2 and reddit_sentiment > 0.2 and "BREAKOUT_CANDIDATE" in flags
    all_negative = sit_count >= 2 and reddit_sentiment < -0.2 and "DECLINING_ROLE" in flags
    if all_positive or all_negative:
        score += 1  # Aligned signals = higher confidence
    
    # Map to conviction
    if score >= 4:
        return "HIGH"
    elif score >= 2:
        return "MEDIUM-HIGH"
    elif score >= 0:
        return "MIXED"
    elif score >= -2:
        return "MEDIUM-LOW"
    return "LOW (concerning)"
```

---

## Enhancement Engine Math

| Flag | Condition |
|------|-----------|
| `BREAKOUT_CANDIDATE` | `L3W_avg > projection × 1.5` |
| `TRENDING_UP` | `L3W_avg > projection × 1.2` |
| `DECLINING_ROLE` | `L3W_avg < projection × 0.7` |
| `HIGH_CEILING` | `L3W_max > projection × 2.0` |
| `CONSISTENT` | `L3W range tight, within ±10% of projection` |

---

## MVP Phases (Jan 11 Target)

| Phase | Scope | Key Deliverable |
|-------|-------|-----------------|
| **1** | Sleeper client, search, enhanced cards | Can look up any player |
| **2** | Trend charts, flags | See L3W charts + flags |
| **3** | Reddit Pulse | Sentiment + top comments |
| **4** | YouTube/Podcast → LLM synthesis | "Expert Takes" section works |

### Post-MVP

| Phase | Scope |
|-------|-------|
| 5 | Comparison view |
| 6 | Flags browser |
| 7 | Export |

---

## Open Questions

1. **Name**: "Fantasy Pulse" confirmed?
2. **LLM**: Use Gemini Flash (fast, cheap) or GPT-4o-mini?
3. **Caching**: Cache transcripts for 24h? Cache LLM extractions per player per video?
4. **Deploy**: Local-only MVP or target Vercel + Railway?
