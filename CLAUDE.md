# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

dbAI Pulse is a Fantasy Football intelligence dashboard that combines Sleeper API data with YouTube transcript analysis, Yahoo Fantasy league integration, and Gemini AI synthesis to provide actionable start/sit recommendations and waiver wire advice.

## Development Commands

### Backend (Python FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload  # http://localhost:8000
```

### Frontend (Vite + React)
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
npm run build  # Production build
npm run lint   # ESLint
```

### Deploy to Railway
```bash
rm -rf frontend/dist  # CRITICAL: stale local builds get uploaded instead of building on Railway
railway up --service "backend" --path-as-root backend --detach
railway up --service "frontend" --path-as-root frontend --detach
```
Always use `--path-as-root` for this monorepo. `VITE_API_BASE_URL` is a build-time variable — must be set in Railway before frontend build.

## Architecture

### Backend Router Registration Order (`backend/main.py`)
Static-path routers are registered **before** the `players` catch-all `/{sleeper_id}` route:
1. `flags.router` → `/api/players` (by-flag, flags endpoints)
2. `comparison.router` → `/api/players` (compare endpoint)
3. `pulse.router` → `/api/players` (pulse AI synthesis)
4. `players.router` → `/api/players` (search, detail, trends)
5. `accounts.router` → `/api/auth` (register, login)
6. `auth.router` → `/api/auth` (session check, logout, Yahoo OAuth callbacks)
7. `yahoo.router` → `/api/yahoo` (teams, roster, waivers, insights)

### Services Layer (`backend/services/`)
- **sleeper.py**: Sleeper API client — player database (cached 72h), projections (5 min TTL), weekly stats (5 min TTL)
- **enhancement.py**: EnhancementEngine — performance flags + adjusted projections from L3W vs projection comparison
- **youtube.py**: YouTube transcript fetching via `youtube-transcript-api`, player mention extraction with context
- **gemini_synthesis.py**: Gemini 2.5 Flash synthesis — combines Sleeper + YouTube data into JSON (recommendation/conviction/reasoning). Includes prompt injection sanitization, conviction capping for sparse data, bye week override to SIT, and offseason detection
- **yahoo.py**: Yahoo Fantasy API client — teams, rosters, league players, waiver wire. Multi-pass player matching (direct ID → stored mapping → fuzzy name → search API)
- **yahoo_token_manager.py**: Yahoo OAuth token refresh/encryption lifecycle
- **roster_insights.py**: AI-generated roster analysis per Yahoo team
- **season_context.py**: Season state detection (regular/playoff/offseason) via Sleeper API
- **player_enrichment.py**: Cross-references Yahoo players with Sleeper data
- **storage.py**: SQLite persistence — WAL mode, thread-safe writes
- **oauth_config.py**: Yahoo OAuth 2.0 with PKCE configuration
- **passwords.py** / **crypto.py**: bcrypt hashing, Fernet token encryption

### Data Flow
1. Player search → Sleeper full player database (cached indefinitely)
2. Player detail → projection + L3W stats from Sleeper → EnhancementEngine flags
3. Pulse → YouTube transcripts + Gemini synthesis → JSON with recommendation/conviction
4. Waiver wire → Yahoo free agents → Sleeper enrichment → Gemini AI scoring → tiered GRAB/WATCH/SKIP

### Frontend Routing
Custom hash-based router (`frontend/src/hooks/useHashRouter.js`) — no external router library.

| Hash | Route | Auth Required |
|------|-------|:---:|
| `#/` | DashboardHome | No |
| `#/search` | PlayerSearch + EnhancedCard + PerformanceChart | No |
| `#/trends` | FlagsBrowser | No |
| `#/compare` | ComparisonView | No |
| `#/roster` | RosterView (Yahoo) | Yes |
| `#/waiver` | WaiverWire (Yahoo) | Yes |

### Auth Flow
- **Local accounts**: bcrypt password hashing, Starlette session middleware (cookie-based)
- **Yahoo OAuth**: PKCE flow — `/api/auth/yahoo/start` → Yahoo consent → `/api/auth/yahoo/callback` → encrypted tokens in SQLite
- Auth-gated routes (roster, waiver) show `AuthPage` component if not logged in

### CSS Architecture
- Dark theme via CSS custom properties defined in `App.css` (e.g., `--bg-primary`, `--text-primary`, `--accent`, `--success`, `--danger`)
- One `.css` file per component, no CSS-in-JS
- Mono font (`--font-mono`) used for stats/data, sans font for prose

### SQLite Database (`data/app.db`)
Ephemeral on Railway (resets on deploy). Tables: `users`, `yahoo_tokens`, `team_feedback_preferences`, `team_insights_cache`, `app_settings`, `yahoo_sleeper_player_map`.

## API Endpoints

### Players (`/api/players`)
- `GET /search?q={name}` — Autocomplete search
- `GET /{sleeper_id}` — Enhanced player with flags + projection
- `GET /{sleeper_id}/trends?lookback=5` — Weekly data for charting
- `GET /{sleeper_id}/pulse` — Full AI synthesis (Gemini + YouTube)
- `GET /compare?ids=id1,id2` — Side-by-side comparison
- `GET /by-flag?flag={flag}&limit=25` — Players by performance flag
- `GET /flags` — All active flags

### Auth (`/api/auth`)
- `GET /me` — Session check
- `POST /logout` — End session
- `POST /register` — Create account
- `POST /login` — Password login
- `GET /yahoo/start` — Begin Yahoo OAuth PKCE flow
- `GET /yahoo/callback` — OAuth redirect handler

### Yahoo (`/api/yahoo`)
- `GET /teams` — User's Yahoo fantasy teams
- `GET /teams/{team_key}/roster` — Team roster with Sleeper enrichment
- `GET /teams/{team_key}/insights` — AI-generated roster analysis
- `GET /leagues/{league_key}/waivers` — Waiver wire with AI recommendations

## Configuration

### Environment Variables (`backend/.env`)
```
GEMINI_API_KEY=         # Required for AI synthesis
YAHOO_CLIENT_ID=        # Yahoo Fantasy OAuth
YAHOO_CLIENT_SECRET=
YAHOO_REDIRECT_URI=
TOKEN_ENCRYPTION_KEY=   # Fernet key for Yahoo token encryption
SESSION_SECRET_KEY=     # Starlette session cookie secret
FRONTEND_ORIGINS=       # Comma-separated CORS origins
```

### Season Config (`backend/config.py`)
`nfl_season` and `nfl_week` control which week's projections/stats are fetched. Update as the season progresses.

## Performance Flags Reference

| Flag | Condition |
|------|-----------|
| BREAKOUT_CANDIDATE | L3W avg > 150% of projection |
| TRENDING_UP | L3W avg > 120% of projection |
| UNDERPERFORMING | L3W avg < 80% of projection |
| DECLINING_ROLE | L3W avg < 70% of projection |
| HIGH_CEILING | Best week > 200% of projection |
| BOOM_BUST | Best week > 2x worst week |
| CONSISTENT | All weeks within +/- 20% of avg |

## Key Dependencies

**Backend**: FastAPI, httpx, pydantic-settings, youtube-transcript-api, google-genai, cachetools, slowapi, bcrypt, cryptography
**Frontend**: React 19, Recharts, Vite 7
