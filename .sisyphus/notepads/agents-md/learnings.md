# Learnings

## Style Section

### Backend (FastAPI / Python)
- **Framework**: FastAPI with `async/await` for all IO-bound operations (endpoints, service calls).
- **Service Pattern**: Services live in `backend/services/` and are accessed via `get_*` singleton helpers (e.g., `get_sleeper_client()`).
- **Models**: Pydantic `BaseModel` for all API schemas. Define in `backend/models/schemas.py`.
- **Router Pattern**: Routers live in `backend/routers/` and use `response_model` decorators for type safety.
- **Naming**: 
  - Functions/Variables: `snake_case`
  - Classes/Models: `PascalCase`
- **Imports**: 
  - 1. Standard library
  - 2. Third-party (FastAPI, Pydantic, httpx)
  - 3. Local modules
- **Documentation**: Triple-quoted docstrings for all modules, classes, and public functions.
- **Error Handling**: 
  - Use `raise_for_status()` in service clients for external APIs.
  - Raise `fastapi.HTTPException` in routers for client-facing errors.
- **Configuration**: `pydantic-settings` used with a `.env` file. Settings are accessed via `get_settings()` singleton.

### Frontend (Vite / React)
- **Framework**: React 19 (JSX, no TypeScript).
- **Organization**: Components in `frontend/src/components/`, each paired with a `.css` file of the same name.
- **State Management**: React Hooks (`useState`, `useCallback`, `useMemo`).
- **Data Fetching**: Native `fetch` API against `http://localhost:8000/api/...`.
- **Naming**:
  - Components: `PascalCase`
  - Variables/Functions: `camelCase`
- **Linting**: ESLint flat config (`eslint.config.js`). 
  - Allows unused vars if they start with Uppercase (Components) or Underscore (args).
- **Modals**: Rendered via `createPortal` to `document.body`.
- **Styling**: Vanilla CSS. Avoid global styles unless in `index.css`.

### General
- **Project Structure**: Clean separation between `backend/` and `frontend/`.
- **Git**: Follow commit message style (usually concise summaries of why changes were made).
- **NFL Data**: `backend/config.py` holds `nfl_season` and `nfl_week` which are the source of truth for all calculations.

## Command Discovery (Build, Lint, Test)
Found the following commands in the repository:

### Frontend (frontend/)
- **Build**: `npm run build` (runs `vite build`)
- **Lint**: `npm run lint` (runs `eslint .`)
- **Dev**: `npm run dev` (runs `vite`)
- **Preview**: `npm run preview` (runs `vite preview`)
- **Tests**: No test runners (Vitest, Jest, etc.) or test files detected in the frontend.

### Backend (backend/)
- **Build**: N/A (Python/FastAPI)
- **Lint**: No linting configuration (flake8, black, etc.) detected.
- **Dev**: `uvicorn main:app --reload` (standard FastAPI dev server)
- **Tests**: No test framework (Pytest, Unittest) or test files detected.

### Root / Global
- **Startup**: `./start.sh` starts both backend and frontend in dev mode.
- **CI/CD**: No CI workflows or test configurations found (confirmed by AGENTS.md).

## Code Style Rules & Conventions

### Backend (Python/FastAPI)
- **Formatting**: 4-space indentation (implicit, PEP 8 style). No explicit config file (e.g., `ruff.toml`) detected.
- **Naming Conventions**:
  - **Classes**: `PascalCase` (e.g., `SleeperClient` in `backend/services/sleeper.py`).
  - **Functions & Variables**: `snake_case` (e.g., `search_players` in `backend/routers/players.py`).
  - **Singletons/Internal Globals**: `_camelCase` with leading underscore (e.g., `_players_cache` in `backend/services/sleeper.py`).
  - **Constants**: `UPPER_SNAKE_CASE` (e.g., `VALID_FLAGS` in `backend/routers/players.py`).
- **Imports**: Ordered as (1) Standard Library, (2) Third-party (FastAPI, httpx, pydantic), (3) Local modules (`config`, `services`, `models`).
- **Error Handling**: Uses `try...except` blocks with `logging` and `HTTPException` for API responses (e.g., `backend/routers/players.py`).
- **Type Hinting**: Heavily used for function signatures and Pydantic models (e.g., `backend/models/schemas.py`).
- **Documentation**: Triple-quoted docstrings for modules and major functions.

### Frontend (React/JSX)
- **Formatting**: **Inconsistent indentation**. `frontend/src/App.jsx` uses 2 spaces, while `frontend/src/components/PlayerSearch.jsx` uses 4 spaces.
- **Linting (Explicit)**: Defined in `frontend/eslint.config.js`.
  - Extends: `js.configs.recommended`, `react-hooks`, `react-refresh`.
  - Custom Rule: `no-unused-vars` allows vars starting with `[A-Z_]` or arguments starting with `_`.
- **Naming Conventions**:
  - **Components**: `PascalCase` (e.g., `PlayerSearch`).
  - **Functions & Variables**: `camelCase` (e.g., `handlePlayerSelect`, `loading`).
  - **CSS Classes**: `kebab-case` (e.g., `player-search`).
- **Component Structure**: `Component.jsx` paired with `Component.css` in the same directory (e.g., `frontend/src/components/PlayerSearch.jsx`).
- **Hooks**: Standard React hooks (`useState`, `useEffect`, `useCallback`, `useRef`) are used extensively.
- **API Calls**: Uses `fetch` against `http://localhost:8000/api/...` with `try...catch` for error handling.



## External AGENTS.md Guidance (2026-01-26)
- OpenCode docs: AGENTS.md provides project rules, recommend committing it, supports project + global rules with precedence and Claude Code fallbacks. Source: https://github.com/anomalyco/opencode/blob/6b83b172ae5969264bebee906178edf82d4d5910/packages/web/src/content/docs/rules.mdx#L6-L95
- GitLab Duo docs: AGENTS.md is an emerging standard; intended to capture repo structure, conventions, build/test instructions; supports user/workspace/subdirectory levels with additive context. Source: https://github.com/gitlabhq/gitlabhq/blob/0338625c4996c8b4dde44bd86d1767b654121ee7/doc/user/gitlab_duo/customize_duo/agents_md.md#L23-L47
- Kilo Code docs: AGENTS.md is described as an open, cross-tool standard; recommends root-level file, uppercase filename, optional subdirectory overrides, and emphasizes portability/consistency. Source: https://github.com/Kilo-Org/kilocode/blob/3d2a8bd12e4d0da09d7863defc5f6eff6823c67a/apps/kilocode-docs/docs/agent-behavior/agents-md.md#L1-L57
- Sentry repo: treats AGENTS.md as the source of truth and points to nested AGENTS.md files for context-aware guidance in subareas, aligning with tool rules that load the right guide per path. Source: https://github.com/getsentry/sentry/blob/ed56323a08a29c4d569f0137abfeef1ecf582ee4/AGENTS.md#L1-L175
## AGENTS.md Update Learnings
- Expanded AGENTS.md to include detailed command lists for both backend and frontend.
- Documented the lack of test infrastructure (no pytest/vitest).
- Codified backend style: Router/Service pattern, async I/O, Pydantic models, specific import order.
- Codified frontend style: JSX only, paired CSS files, React 19 hooks, createPortal for modals.
- Noted ESLint exceptions for unused variables starting with [A-Z_] or _.
- Included performance flag definitions as shared semantic vocabulary.
Expanded AGENTS.md to include detailed development workflow and style conventions for both backend and frontend. Added specifics on Pydantic models, async patterns, React component structure, and performance flag definitions.
Expanded AGENTS.md to ~150 lines by adding sections on API Practices, Frontend Data Flow, Manual QA, and Environment details. Maintained existing facts and structure.
