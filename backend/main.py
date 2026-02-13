"""
dbAI Pulse - Fantasy Football Intelligence Dashboard
FastAPI Backend
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from routers import accounts, players, comparison, flags, pulse, auth, yahoo
from services.storage import get_storage

load_dotenv()
settings = get_settings()

app = FastAPI(
    title="dbAI Pulse",
    description="Fantasy Football Intelligence Dashboard with AI-powered expert synthesis",
    version="0.1.0",
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Detect local dev (any non-HTTPS origin means we're not in production)
_is_local = any(o.startswith("http://") for o in settings.frontend_origin_list)

# Middleware is applied in reverse order — last added = outermost.
# SessionMiddleware must be INNER so CORSMiddleware handles OPTIONS preflight first.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=not _is_local,
    same_site="lax" if _is_local else "none",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Register static-path routers BEFORE players.router so /by-flag, /flags,
# /compare are matched before the /{sleeper_id} catch-all in players.
app.include_router(flags.router, prefix="/api/players", tags=["flags"])
app.include_router(comparison.router, prefix="/api/players", tags=["comparison"])
app.include_router(pulse.router, prefix="/api/players", tags=["pulse"])
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
