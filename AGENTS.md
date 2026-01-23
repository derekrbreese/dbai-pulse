# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-22 04:35:26 EST
**Commit:** 35260ea
**Branch:** master

## OVERVIEW
dbAI Pulse is a fantasy football intelligence dashboard with a FastAPI backend that aggregates Sleeper data, YouTube transcripts, and Gemini synthesis, plus a Vite React frontend that consumes the API.

## STRUCTURE
dbai-pulse/
├── backend/             # FastAPI API + services
├── frontend/            # Vite React client
├── project-management/  # planning docs
├── start.sh             # local convenience runner
├── README.md
└── CLAUDE.md            # repo-specific dev guidance

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| API endpoints | backend/routers/players.py | All player search/pulse/compare routes |
| Backend entry + CORS | backend/main.py | FastAPI app + router wiring |
| Sleeper API client | backend/services/sleeper.py | Projections, stats, caching |
| Performance flags | backend/services/enhancement.py | Flag + adjusted projection logic |
| Gemini synthesis | backend/services/gemini_synthesis.py | Prompt + JSON extraction |
| YouTube transcripts | backend/services/youtube.py | Transcript fetch + mention extraction |
| Settings/env | backend/config.py | nfl_season/nfl_week + env vars |
| Pydantic schemas | backend/models/schemas.py | API response models |
| Frontend entry | frontend/src/main.jsx | React root |
| App shell | frontend/src/App.jsx | Main layout + fetches |
| UI components | frontend/src/components | Cards, modals, charts |
| Global styles | frontend/src/index.css | Base styles |
| App styles | frontend/src/App.css | App-level layout styles |
| Planning docs | project-management | Phase plans and walkthroughs |

## CONVENTIONS
- Frontend is JSX (no TS) with paired `Component.jsx` + `Component.css`.
- Frontend fetches backend at `http://localhost:8000/api/...`.
- Backend uses FastAPI routers + service modules; settings via `backend/config.py`.

## ANTI-PATTERNS (THIS PROJECT)
- None documented.

## UNIQUE STYLES
- Performance flags are the shared semantic vocabulary for backend + UI.
- `nfl_season` and `nfl_week` in `backend/config.py` gate all projections/stats.

## COMMANDS
```bash
./start.sh

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

cd frontend
npm install
npm run dev
npm run build
npm run lint
```

## NOTES
- Backend reads `.env` (Gemini/Reddit keys). Keep secrets out of git.
- Update `backend/config.py` when the NFL week advances.
- No CI workflows or test configs detected.
