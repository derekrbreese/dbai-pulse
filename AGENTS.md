# dbAI Pulse Agent Guide

**Scope:** Repository-level conventions for automated agents

## Project Overview

dbAI Pulse is a fantasy football intelligence dashboard combining:
- **Backend:** FastAPI (Python) - Sleeper projections, YouTube transcripts, Gemini synthesis
- **Frontend:** Vite + React (JavaScript) - Dashboard UI with charts and modals

## Repo Structure

```
backend/           # FastAPI app (routers, services, models)
frontend/          # Vite React client (components, styles)
project-management/ # Planning docs
start.sh           # Runs both backend + frontend
```

## Commands

### Quick Start
```bash
./start.sh                              # Start everything
```

### Backend (FastAPI)
```bash
cd backend
source .venv/bin/activate               # Activate venv (create with: python -m venv .venv)
pip install -r requirements.txt         # Install deps
uvicorn main:app --reload --port 8000   # Run dev server
```

### Frontend (Vite + React)
```bash
cd frontend
npm install                             # Install deps
npm run dev                             # Dev server (localhost:5173)
npm run build                           # Production build
npm run lint                            # ESLint check
npm run preview                         # Preview production build
```

### Testing
- **No test runner configured** (no pytest, vitest, or jest)
- Manual verification: `http://localhost:8000/docs` (API) and `http://localhost:5173` (UI)

## Key Files

| Purpose | File |
|---------|------|
| API routes | `backend/routers/players.py` |
| App entry + CORS | `backend/main.py` |
| Settings + env | `backend/config.py` |
| Pydantic schemas | `backend/models/schemas.py` |
| Sleeper client | `backend/services/sleeper.py` |
| Enhancement engine | `backend/services/enhancement.py` |
| Gemini synthesis | `backend/services/gemini_synthesis.py` |
| YouTube transcripts | `backend/services/youtube.py` |
| React entry | `frontend/src/main.jsx` |
| App shell | `frontend/src/App.jsx` |
| Components | `frontend/src/components/*.jsx` |

## Backend Conventions (Python/FastAPI)

### Architecture
- **Router/Service/Model** separation
- Routers in `backend/routers/` - async FastAPI endpoints
- Services in `backend/services/` - business logic with `get_*` singleton helpers
- Models in `backend/models/schemas.py` - Pydantic request/response bodies

### Code Style
- **Type hints:** Required on all function signatures
- **Docstrings:** Triple-quoted for modules, classes, and public functions
- **Async:** Use `async`/`await` for all external calls (httpx, Gemini, YouTube)
- **Logging:** `logger = logging.getLogger(__name__)` at module scope
- **Errors:** Raise `fastapi.HTTPException` for client errors; log stack traces for 500s
- **Caching:** Use `cachetools.TTLCache` for external API calls

### Import Order
```python
# 1. Standard library
from typing import List, Optional

# 2. Third-party
from fastapi import APIRouter, HTTPException

# 3. Local modules
from config import get_settings
from services.sleeper import get_sleeper_client
```

### Naming
- Functions: `snake_case` (e.g., `get_player_projection`)
- Classes: `PascalCase` (e.g., `SleeperClient`, `PlayerBase`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `VALID_FLAGS`)

## Frontend Conventions (React/JavaScript)

### Architecture
- **Language:** JavaScript only (no TypeScript)
- **Components:** Functional components only, no class components
- **Component pairing:** `Component.jsx` with `Component.css` in same folder
- **Modals:** Render via `createPortal(..., document.body)`

### Code Style
- **No semicolons** (consistent throughout)
- **Indentation:** 4-space in component files
- **Strings:** Single quotes for imports, double quotes in JSX attributes
- **API calls:** Use `fetch` with `try/catch/finally` and `response.ok` checks

### Import Order
```javascript
// 1. React hooks
import { useState, useEffect, useCallback } from 'react'

// 2. Local components
import PlayerSearch from './components/PlayerSearch'

// 3. CSS
import './App.css'
```

### Naming
- Components: `PascalCase` (e.g., `PlayerSearch`, `EnhancedCard`)
- Functions: `camelCase` (e.g., `handlePlayerSelect`, `getPositionColor`)
- CSS classes: `kebab-case` (e.g., `player-search`, `search-input-wrapper`)
- Props: `camelCase` (e.g., `onPlayerSelect`, `playerId`)

### ESLint Rules
- Config: `frontend/eslint.config.js` (flat config)
- `no-unused-vars`: Ignores vars matching `^[A-Z_]` and args matching `^_`
- React Hooks and React Refresh plugins enabled

## Environment & Secrets

Backend uses `.env` in `backend/` directory (never commit):
```
GEMINI_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USERNAME=your_username
```

Season/week controlled in `backend/config.py` via `nfl_season` and `nfl_week`.

## Data Flow

1. Search UI calls `GET /api/players/search?q=...`
2. Backend fetches Sleeper projections/stats
3. Enhancement engine applies performance flags
4. UI renders cards and charts
5. Pulse feature adds Gemini synthesis + YouTube context

## Performance Flags

| Flag | Trigger |
|------|---------|
| `BREAKOUT_CANDIDATE` | L3W avg > 150% of projection |
| `TRENDING_UP` | L3W avg > 120% of projection |
| `UNDERPERFORMING` | L3W avg < 80% of projection |
| `DECLINING_ROLE` | L3W avg < 70% of projection |
| `HIGH_CEILING` | Best week > 200% of projection |
| `BOOM_BUST` | Best week > 2x worst week |
| `CONSISTENT` | All weeks within +/- 20% of avg |

## Error Handling Patterns

### Backend
```python
try:
    result = await external_api_call()
except Exception as e:
    logger.error(f"API call failed: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

### Frontend
```javascript
try {
    const response = await fetch(url)
    if (!response.ok) {
        throw new Error('Request failed')
    }
    const data = await response.json()
} catch (err) {
    setError(err.message)
} finally {
    setLoading(false)
}
```

## Anti-Patterns to Avoid

- Do not add TypeScript to frontend
- Do not use class components in React
- Do not commit `.env` files
- Do not add semicolons to JavaScript files
- Do not skip type hints in Python functions
