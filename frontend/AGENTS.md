# FRONTEND KNOWLEDGE BASE

**Generated:** 2026-01-22 04:35:26 EST
**Commit:** 35260ea
**Branch:** master

## OVERVIEW
Vite + React frontend that renders the dashboard UI and calls the FastAPI backend directly.

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| React entry | frontend/src/main.jsx | Mounts `App` |
| App shell | frontend/src/App.jsx | Layout + player fetch flow |
| Base styles | frontend/src/index.css | Global styles |
| App styles | frontend/src/App.css | Layout + page sections |
| UI components | frontend/src/components | Feature UI with paired CSS |
| ESLint config | frontend/eslint.config.js | Flat config + React hooks |
| Vite config | frontend/vite.config.js | React plugin wiring |
| Charting | frontend/src/components/PerformanceChart.jsx | Recharts config |
| Pulse UI | frontend/src/components/PulseButton.jsx | Opens Pulse modal |
| Comparison UI | frontend/src/components/ComparisonView.jsx | Head-to-head modal |
| Trends UI | frontend/src/components/FlagsBrowser.jsx | Flag browser modal |

## CONVENTIONS
- Components pair `Component.jsx` with `Component.css` in `frontend/src/components`.
- Modals render via `createPortal(..., document.body)`.
- API calls use `fetch` against `http://localhost:8000/api/...`.
- Codebase is JSX (no TypeScript).
- ESLint flat config ignores `dist` and allows unused args prefixed with `_`.

## ANTI-PATTERNS (THIS PROJECT)
- None documented.

## NOTES
- Vite dev server runs at `http://localhost:5173` by default.
