# Draft Strategies & Yahoo Integration Plan

**Created:** 2026-01-26
**Status:** Draft
**Scope:** Add draft intelligence to player cards + integrate Yahoo Fantasy API for user rosters

## Executive Summary

Enhance dbAI Pulse with two major capabilities:
1. **Draft Intelligence** - Add ADP, draft value indicators, and tier information to player cards
2. **Yahoo Fantasy Integration** - Allow users to connect their Yahoo Fantasy leagues to see personalized roster analysis

## Phase 1: Draft Data Infrastructure

### 1.1 ADP Data Service
**Goal:** Create a service to fetch and cache Average Draft Position data

**Data Sources (Priority Order):**
1. **Fantasy Football Calculator API** (FREE, REST, JSON)
   - Endpoint: `https://fantasyfootballcalculator.com/api/v1/adp/{format}?teams={n}&year={year}`
   - Formats: standard, ppr, half-ppr, 2qb
   - No auth required
   
2. **Sleeper Draft Picks** (Computed)
   - Use existing Sleeper API to aggregate public draft picks
   - Compute ADP from real user drafts

**Tasks:**
- [ ] Create `backend/services/adp.py` with `ADPService` class following singleton pattern
- [ ] Add ADP cache TTL to `backend/config.py` (recommend 6 hours)
- [ ] Implement Fantasy Football Calculator client
- [ ] Create Pydantic models for ADP data in `backend/models/schemas.py`
- [ ] Add ADP endpoint: `GET /api/players/{sleeper_id}/adp`

### 1.2 Draft Value Calculations
**Goal:** Calculate draft value indicators from ADP data

**Metrics to Add:**
| Metric | Calculation | Display |
|--------|-------------|---------|
| ADP Rank | Raw ADP position | "ADP: 24" |
| Position ADP | ADP within position | "RB12" |
| Value Score | (ECR - ADP) | "+5 value" / "-3 reach" |
| Tier | Cluster analysis on projections | "Tier 1 RB" |
| Draft Range | ADP std deviation | "Rounds 2-3" |

**Tasks:**
- [ ] Add draft value calculations to `backend/services/enhancement.py`
- [ ] Create new draft-related flags: `DRAFT_VALUE`, `DRAFT_REACH`, `RISING_ADP`, `FALLING_ADP`
- [ ] Update `EnhancedPlayer` schema with draft fields
- [ ] Add draft section to `EnhancedCard.jsx`

### 1.3 Tier System
**Goal:** Implement positional tier rankings

**Approach:**
- Use projection clustering to identify tier breaks
- Display tier membership on player cards
- Show "next tier" players for draft strategy

**Tasks:**
- [ ] Implement tier calculation algorithm in `backend/services/tiers.py`
- [ ] Create tier visualization component for frontend
- [ ] Add tier-based browsing to FlagsBrowser

---

## Phase 2: Yahoo Fantasy API Integration

### 2.1 OAuth2 Authentication Flow
**Goal:** Allow users to connect their Yahoo Fantasy accounts

**Library:** `yfpy` (GPL-3.0) - Python wrapper for Yahoo Fantasy Sports API

**OAuth Flow:**
1. User clicks "Connect Yahoo" button
2. Backend redirects to Yahoo OAuth consent screen
3. Yahoo redirects back with auth code
4. Backend exchanges code for access/refresh tokens
5. Tokens stored securely (encrypted in session or DB)

**Tasks:**
- [ ] Add Yahoo OAuth credentials to `backend/config.py`:
  - `yahoo_client_id`
  - `yahoo_client_secret`
  - `yahoo_redirect_uri`
- [ ] Create `backend/services/yahoo.py` with `YahooFantasyService`
- [ ] Implement OAuth endpoints:
  - `GET /api/auth/yahoo/login` - Initiate OAuth flow
  - `GET /api/auth/yahoo/callback` - Handle OAuth callback
  - `GET /api/auth/yahoo/status` - Check connection status
  - `POST /api/auth/yahoo/disconnect` - Revoke access

### 2.2 League & Roster Data
**Goal:** Fetch user's fantasy leagues and rosters

**Available Data from Yahoo API (via YFPY):**
- User's leagues across seasons
- Team rosters (current week, season)
- Draft results with pick positions
- Player ownership percentages
- Matchup data

**Key YFPY Methods:**
```python
query = YahooFantasySportsQuery(league_id="######", game_code="nfl")
query.get_team_roster_player_stats(team_id)  # Full roster with stats
query.get_league_draft_results()              # Draft picks
query.get_team_roster_player_info_by_week(team_id, week)
```

**Tasks:**
- [ ] Create roster sync endpoint: `GET /api/yahoo/leagues`
- [ ] Create roster endpoint: `GET /api/yahoo/leagues/{league_id}/roster`
- [ ] Map Yahoo player IDs to Sleeper IDs (create mapping table/service)
- [ ] Cache roster data with appropriate TTL

### 2.3 Roster Integration UI
**Goal:** Display user's Yahoo roster within dbAI Pulse

**UI Components:**
- [ ] "My Roster" section in header/navigation
- [ ] League selector dropdown (for users in multiple leagues)
- [ ] Roster view showing all players with dbAI Pulse enhancements
- [ ] Quick-compare feature between roster players

**Tasks:**
- [ ] Create `frontend/src/components/YahooConnect.jsx` - OAuth button
- [ ] Create `frontend/src/components/RosterView.jsx` - Roster display
- [ ] Create `frontend/src/components/LeagueSelector.jsx` - League picker
- [ ] Update App.jsx with roster navigation

---

## Phase 3: Draft Strategy Features

### 3.1 Draft Assistant
**Goal:** Provide real-time draft recommendations

**Features:**
- Best available by position
- Value picks (ADP vs current pick)
- Team needs analysis (based on roster)
- Tier alerts ("Last Tier 1 RB available!")

**Tasks:**
- [ ] Create `backend/services/draft_assistant.py`
- [ ] Create draft mode UI with live recommendations
- [ ] Integrate with Yahoo live draft (if API supports)

### 3.2 Mock Draft Analysis
**Goal:** Analyze completed drafts for grade/value

**Features:**
- Draft grade calculation
- Value over ADP analysis
- Team strength by position
- Improvement suggestions

**Tasks:**
- [ ] Create draft analysis endpoint: `POST /api/draft/analyze`
- [ ] Create draft report component
- [ ] Support importing Yahoo draft results

---

## Technical Architecture

### New Files to Create

**Backend:**
```
backend/
├── services/
│   ├── adp.py           # ADP data fetching
│   ├── yahoo.py         # Yahoo Fantasy API wrapper
│   ├── tiers.py         # Tier calculations
│   └── draft_assistant.py
├── routers/
│   ├── auth.py          # OAuth endpoints
│   └── yahoo.py         # Yahoo data endpoints
└── models/
    └── schemas.py       # (update with draft/yahoo models)
```

**Frontend:**
```
frontend/src/components/
├── YahooConnect.jsx     # OAuth button
├── YahooConnect.css
├── RosterView.jsx       # Roster display
├── RosterView.css
├── LeagueSelector.jsx   # League picker
├── LeagueSelector.css
├── DraftSection.jsx     # Draft info on player card
└── DraftSection.css
```

### Dependencies to Add

**Backend (requirements.txt):**
```
yfpy>=16.0.0            # Yahoo Fantasy API wrapper
```

**Note:** YFPY is GPL-3.0 licensed - ensure compatibility with project license.

### Environment Variables

Add to `backend/.env`:
```
YAHOO_CLIENT_ID=your_yahoo_client_id
YAHOO_CLIENT_SECRET=your_yahoo_client_secret
YAHOO_REDIRECT_URI=http://localhost:8000/api/auth/yahoo/callback
```

---

## Implementation Priority

### MVP (Phase 1 + 2.1-2.2): 
**Goal:** Draft data on player cards + Yahoo roster sync

1. ADP Service (Fantasy Football Calculator)
2. Draft fields on EnhancedPlayer schema
3. Draft section on player cards
4. Yahoo OAuth flow
5. Roster fetching and display

### Post-MVP (Phase 2.3 + 3):
- Live draft assistant
- Mock draft analysis
- Tier visualization
- Multi-league support

---

## Risk & Considerations

| Risk | Mitigation |
|------|------------|
| Yahoo OAuth complexity | Use YFPY which handles token refresh |
| Player ID mapping (Yahoo ↔ Sleeper) | Build mapping service using player names/teams |
| YFPY GPL license | Review license compatibility; isolate if needed |
| Rate limits | Implement caching (TTLCache pattern already in use) |
| Off-season data availability | Graceful fallbacks when draft data unavailable |

---

## Success Metrics

- [ ] Player cards show ADP and draft value indicators
- [ ] Users can connect Yahoo Fantasy account
- [ ] Users can view their roster with dbAI Pulse enhancements
- [ ] Draft value calculations match industry standards
