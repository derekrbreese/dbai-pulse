# Phase 8: Yahoo League Integration

## Summary
Add Yahoo Fantasy Football league sync to dbAI Pulse. Users can view their roster with enhanced insights, get waiver wire recommendations, and receive start/sit guidance - all powered by the existing enhancement engine and Gemini AI.

## Authentication Strategy
1. **Primary**: Read tokens from MCP server's storage (`~/.yahoo-fantasy/tokens.json`)
2. **Fallback**: Manual token input via settings modal (quick MVP)

## Features
- **My League**: View league standings, matchups
- **My Roster**: See roster with flags, projections, Pulse analysis
- **Waiver Wire**: AI-powered pickup recommendations
- **Start/Sit**: Lineup optimization using Gemini

---

## Implementation

### Phase 8.1: Backend - Yahoo Service + Auth

**New File: `backend/services/yahoo.py`**
```python
class YahooClient:
    """Yahoo Fantasy API client - reuses MCP OAuth tokens"""

    TOKEN_PATH = "~/.yahoo-fantasy/tokens.json"  # MCP token location

    async def get_token() -> Optional[str]
    async def get_leagues() -> List[LeagueInfo]
    async def get_roster(league_key: str, team_key: str) -> List[RosterPlayer]
    async def get_waiver_wire(league_key: str, position: str) -> List[WaiverPlayer]
    async def get_matchup(league_key: str, week: int) -> MatchupInfo
```

**New File: `backend/routers/leagues.py`**
```python
@router.get("/leagues")                    # List user's leagues
@router.get("/leagues/{key}")              # League details + standings
@router.get("/leagues/{key}/roster")       # User's roster with enhancements
@router.get("/leagues/{key}/waiver")       # Waiver wire with rankings
@router.get("/leagues/{key}/matchup")      # Current week matchup
@router.post("/leagues/{key}/optimize")    # Gemini lineup optimization
```

**Update: `backend/models/schemas.py`**
- Add: `YahooLeague`, `YahooTeam`, `RosterSlot`, `WaiverCandidate`

**Update: `backend/main.py`**
- Include leagues router: `app.include_router(leagues.router, prefix="/api/leagues")`

### Phase 8.2: Frontend - League View Modal

**New File: `frontend/src/components/LeagueView.jsx`**
- Modal overlay (follows ComparisonView pattern)
- Tabs: Roster | Waiver Wire | Matchup
- Roster tab shows players with flags + quick Pulse preview
- Waiver tab shows top pickups ranked by value
- Matchup tab shows projected vs opponent

**New File: `frontend/src/components/LeagueView.css`**
- Dark theme styling consistent with app
- Tab navigation
- Roster grid layout

**Update: `frontend/src/App.jsx`**
- Add "My League" button in header
- Add `showLeagueView` state
- Render LeagueView modal when active

### Phase 8.3: Enhanced Roster Display

**New File: `frontend/src/components/RosterCard.jsx`**
- Compact player card for roster view
- Shows: position slot, player name, projection, flags
- Click to load full EnhancedCard + Pulse

**Integration with existing components:**
- Reuse `EnhancedCard` for detailed player view
- Reuse `PerformanceChart` for trends
- Reuse `PulseModal` for AI analysis

### Phase 8.4: Waiver Wire Intelligence

**Backend enhancement:**
- Cross-reference Yahoo waiver wire with Sleeper projections
- Apply enhancement engine to all waiver candidates
- Rank by: projection + flag score + trend

**Frontend display:**
- Sortable table: Name, Position, Owned%, Projection, Flags
- Click player to see full Pulse analysis
- "Add" action (future: direct add via Yahoo API)

---

## Files to Create
1. `backend/services/yahoo.py` - Yahoo API client
2. `backend/routers/leagues.py` - League endpoints
3. `frontend/src/components/LeagueView.jsx` - Main modal
4. `frontend/src/components/LeagueView.css` - Styling
5. `frontend/src/components/RosterCard.jsx` - Compact roster display

## Files to Modify
1. `backend/main.py` - Include leagues router
2. `backend/models/schemas.py` - Add Yahoo models
3. `frontend/src/App.jsx` - Add League nav button + modal

---

## Data Flow

```
User clicks "My League"
    ↓
LeagueView fetches /api/leagues
    ↓
Backend reads ~/.yahoo-fantasy/tokens.json (MCP tokens)
    ↓
Backend calls Yahoo API → gets roster
    ↓
For each player: cross-reference Sleeper → get projections
    ↓
Apply EnhancementEngine → calculate flags
    ↓
Return enhanced roster to frontend
    ↓
Display with RosterCard components (flags, projections)
    ↓
Click player → loads full EnhancedCard + Pulse
```

---

## MVP Scope (Phase 8.1 + 8.2)
- [ ] Yahoo token reading (MCP + manual input)
- [ ] League list endpoint
- [ ] Roster endpoint with basic enhancement
- [ ] LeagueView modal with roster display
- [ ] Click-to-select player integration

## Future Enhancements
- Lineup optimization via Gemini
- Trade analyzer
- Weekly projections comparison
- Injury alerts for roster players
