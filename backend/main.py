"""
dbAI Pulse - Fantasy Football Intelligence Dashboard
FastAPI Backend
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from routers import accounts, players, auth, yahoo
from services.storage import get_storage

load_dotenv()
settings = get_settings()

app = FastAPI(
    title="dbAI Pulse",
    description="Fantasy Football Intelligence Dashboard with AI-powered expert synthesis",
    version="0.1.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=True,
    same_site="none",
)

# Include routers
app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(accounts.router, prefix="/api/auth", tags=["accounts"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(yahoo.router, prefix="/api/yahoo", tags=["yahoo"])


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize local persistence on application startup."""
    get_storage().initialize()


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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Return empty favicon response to avoid noisy 404 logs."""
    return Response(status_code=204)
