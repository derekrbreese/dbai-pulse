# BACKEND KNOWLEDGE BASE

**Generated:** 2026-01-22 04:35:26 EST
**Commit:** 35260ea
**Branch:** master

## OVERVIEW
FastAPI backend serving player search, trends, pulse, and comparison endpoints with services for Sleeper, YouTube transcripts, and Gemini synthesis.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| API routes | backend/routers/players.py | All player endpoints live here |
| App entry + CORS | backend/main.py | FastAPI app wiring |
| Settings/env | backend/config.py | pydantic-settings + season/week |
| Schemas/models | backend/models/schemas.py | Pydantic response models |
| Sleeper integration | backend/services/sleeper.py | Async HTTP client + caches |
| Flags + adjustments | backend/services/enhancement.py | Performance flag rules |
| Gemini synthesis | backend/services/gemini_synthesis.py | Prompt + JSON extraction |
| YouTube transcripts | backend/services/youtube.py | Transcript fetch + mention extraction |

## CONVENTIONS
- Routers live in `backend/routers` and expose async FastAPI endpoints.
- Services live in `backend/services` with `get_*` helpers returning singletons.
- Sleeper projections/stats are cached in module-level dicts with TTLs from `backend/config.py`.

## ANTI-PATTERNS (THIS PROJECT)
- None documented.

## NOTES
- `nfl_season` and `nfl_week` are the central knobs for data freshness.
- `.env` is loaded via `pydantic-settings` in `backend/config.py`.
