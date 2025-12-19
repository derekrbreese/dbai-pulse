# Phase 5: Comparison View - Implementation Plan

## Overview
"Should I start Player A or Player B?" - Side-by-side player comparison with Gemini-powered head-to-head analysis.

---

## UI Design

```
┌─────────────────────────────────────────────────────────────────┐
│  🔄 Compare Players                                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐          ┌─────────────────┐              │
│  │ Search Player A │    VS    │ Search Player B │              │
│  └─────────────────┘          └─────────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐              ┌─────────────┐                   │
│  │  Player A   │              │  Player B   │                   │
│  │  Card       │     ⚡       │  Card       │                   │
│  │  Stats      │              │  Stats      │                   │
│  └─────────────┘              └─────────────┘                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  🏆 HEAD-TO-HEAD ANALYSIS (Gemini)                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Winner: Player A                                            ││
│  │ Conviction: HIGH                                            ││
│  │ Reasoning: "Player A has a better matchup and..."           ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### Frontend

#### 1. ComparisonView.jsx
Main container with two player slots and comparison results.

#### 2. PlayerSlot.jsx  
Reusable search + display component for each player.

#### 3. ComparisonResult.jsx
Displays Gemini's head-to-head analysis with winner highlight.

---

### Backend

#### New Endpoint: `/api/players/compare`

```python
@router.post("/compare")
async def compare_players(player_a_id: str, player_b_id: str):
    """
    Compare two players using Gemini with Google Search grounding.
    Returns winner recommendation with reasoning.
    """
```

#### Response Schema
```python
class ComparisonResult(BaseModel):
    player_a: EnhancedPlayer
    player_b: EnhancedPlayer
    winner: str  # "A" | "B" | "TOSS_UP"
    winner_name: str
    conviction: str  # "HIGH" | "MEDIUM" | "LOW"
    reasoning: str
    key_advantages_a: List[str]
    key_advantages_b: List[str]
    matchup_edge: str  # Who has better matchup
    sources_used: List[str]
```

---

## Implementation Steps

### Step 1: Backend Comparison Endpoint
- [ ] Add `ComparisonResult` schema to `models/schemas.py`
- [ ] Create comparison endpoint in `routers/players.py`
- [ ] Add Gemini comparison method in `gemini_synthesis.py`

### Step 2: Frontend Components
- [ ] Create `ComparisonView.jsx` with two player slots
- [ ] Add `PlayerSlot.jsx` for reusable search
- [ ] Create `ComparisonResult.jsx` for winner display
- [ ] Add CSS with split-screen layout

### Step 3: Navigation
- [ ] Add "Compare" button/tab to main UI
- [ ] Route handling for comparison mode

---

## Gemini Comparison Prompt

```
Compare these two fantasy football players for Week 16:

PLAYER A: {player_a_name} ({position})
- Projection: {proj_a} pts
- L3W Average: {avg_a} pts
- Trend: {trend_a}
- Flags: {flags_a}

PLAYER B: {player_b_name} ({position})  
- Projection: {proj_b} pts
- L3W Average: {avg_b} pts
- Trend: {trend_b}
- Flags: {flags_b}

Use Google Search to find current matchup info, injury news, and expert rankings.

Return JSON:
{
    "winner": "A" | "B" | "TOSS_UP",
    "conviction": "HIGH" | "MEDIUM" | "LOW", 
    "reasoning": "2-3 sentences explaining the pick",
    "key_advantages_a": ["advantage 1", "advantage 2"],
    "key_advantages_b": ["advantage 1", "advantage 2"],
    "matchup_edge": "A has easier matchup vs ..." | "B has easier matchup vs ...",
    "sources_used": ["source 1", "source 2"]
}
```

---

## Success Criteria
- Users can search and select two players
- Side-by-side display of stats/projections
- Gemini provides winner with reasoning
- Clear visual indication of recommended player
