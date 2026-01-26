"""
dbAI Pulse - Fantasy Football Intelligence Dashboard
FastAPI Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers import players, auth, yahoo

load_dotenv()

app = FastAPI(
    title="dbAI Pulse",
    description="Fantasy Football Intelligence Dashboard with AI-powered expert synthesis",
    version="0.1.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(yahoo.router, prefix="/api/yahoo", tags=["yahoo"])


@app.get("/")
async def root():
    return {
        "name": "dbAI Pulse",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
