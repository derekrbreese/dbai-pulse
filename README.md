# dbAI Pulse

A standalone Fantasy Football intelligence dashboard with AI-powered expert synthesis.

## Features

- **Player Search**: Look up any NFL player with enhanced projections
- **Performance Flags**: BREAKOUT_CANDIDATE, TRENDING_UP, DECLINING_ROLE, etc.
- **Trend Charts**: L3W performance visualization
- **The Pulse**: Synthesized expert takes from YouTube/podcasts + Reddit sentiment

## Tech Stack

- **Backend**: Python FastAPI
- **Frontend**: Vite + React
- **Data**: Sleeper API (projections/stats), Reddit API (sentiment), YouTube transcripts
- **AI**: Gemini 3.0 Flash (expert take extraction)

## Setup

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

Create `backend/.env`:
```
GEMINI_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USERNAME=your_username
```

## License

MIT
