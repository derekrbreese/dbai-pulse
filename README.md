# dbAI Pulse

[![GitHub](https://img.shields.io/badge/GitHub-derekrbreese%2Fdbai--pulse-blue?logo=github)](https://github.com/derekrbreese/dbai-pulse)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
YAHOO_CLIENT_ID=your_yahoo_client_id
YAHOO_CLIENT_SECRET=your_yahoo_client_secret
YAHOO_REDIRECT_URI=https://your-domain.example/api/auth/yahoo/callback
SESSION_SECRET_KEY=replace_with_long_random_secret
TOKEN_ENCRYPTION_KEY=replace_with_fernet_key
```

## Account Login (Yahoo Features Only)

The app keeps player search/trends open, and requires local account login only for Yahoo/team features:

1. Open the app and create an account or sign in
2. Keep that browser session active
3. Connect Yahoo from the setup page after login

## Yahoo OAuth Setup (Required For Team Import)

If you see `Yahoo OAuth not configured`, configure Yahoo app credentials:

1. Create a Yahoo developer app:
   - Go to [Yahoo Developer Apps](https://developer.yahoo.com/apps/)
   - Create/select an app with Fantasy Sports read scope
2. Set callback URL in Yahoo app (must be public HTTPS):
   - `https://your-domain.example/api/auth/yahoo/callback`
   - It must exactly match `YAHOO_REDIRECT_URI`
3. Copy Yahoo credentials into `backend/.env`:
   - `YAHOO_CLIENT_ID`
   - `YAHOO_CLIENT_SECRET`
   - `YAHOO_REDIRECT_URI=https://your-domain.example/api/auth/yahoo/callback`
4. Set session and token encryption secrets:
   - `SESSION_SECRET_KEY` should be a long random string
   - `TOKEN_ENCRYPTION_KEY` should be a Fernet key
5. Generate a Fernet key (example):
```bash
cd backend
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
6. Restart backend after updating `.env`:
```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```

## License

MIT
