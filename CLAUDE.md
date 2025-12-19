# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

dbAI Pulse is a Fantasy Football intelligence dashboard that combines Sleeper API data with YouTube transcript analysis and Gemini AI synthesis to provide actionable start/sit recommendations.

## Development Commands

### Backend (Python FastAPI)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn main:app --reload  # Runs on http://localhost:8000
```

### Frontend (Vite + React)
```bash
cd frontend
npm install
npm run dev    # Runs on http://localhost:5173
npm run build  # Production build
npm run lint   # ESLint
```

## Architecture

### Backend Services Layer (`backend/services/`)
- **sleeper.py**: Sleeper API client - fetches player data, projections, and weekly stats. Uses in-memory TTL caches for projections (5 min) and stats.
- **enhancement.py**: EnhancementEngine calculates performance flags (BREAKOUT_CANDIDATE, TRENDING_UP, DECLINING_ROLE, etc.) and adjusted projections by comparing L3W averages to Sleeper projections.
- **youtube.py**: Fetches YouTube transcripts via `youtube-transcript-api`, extracts player mentions with surrounding context.
- **gemini_synthesis.py**: Uses Gemini 3 Flash to synthesize player analysis from Sleeper data + YouTube context into JSON with recommendation/conviction/reasoning.

### Data Flow
1. Player search uses Sleeper's full player database (cached indefinitely)
2. Player detail fetches projection + L3W stats from Sleeper
3. EnhancementEngine calculates flags based on projection vs recent performance
4. Pulse endpoint adds YouTube transcript analysis + Gemini AI synthesis

### API Endpoints (`backend/routers/players.py`)
- `GET /api/players/search?q={name}` - Search players
- `GET /api/players/{sleeper_id}` - Enhanced player data with flags
- `GET /api/players/{sleeper_id}/trends` - Weekly data for charting
- `GET /api/players/{sleeper_id}/pulse` - Full AI synthesis (Gemini + YouTube)

### Frontend Components (`frontend/src/components/`)
- **PlayerSearch**: Autocomplete search against backend
- **EnhancedCard**: Displays player projection, flags, context
- **PerformanceChart**: Recharts L5W visualization
- **PulseButton/PulseModal**: Triggers and displays Gemini AI analysis

## Configuration

### Environment Variables (`backend/.env`)
```
GEMINI_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USERNAME=your_username
```

### NFL Season Config (`backend/config.py`)
Update `nfl_season` and `nfl_week` as the season progresses - these control which week's projections and stats are fetched.

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

**Backend**: FastAPI, httpx, pydantic-settings, youtube-transcript-api, google-genai, cachetools
**Frontend**: React 19, Recharts, Vite 7
