import logging
import sys
import threading

# Several modules print emoji/Cyrillic status lines (this file included). On
# Windows, stdout defaults to the system codepage (cp1252) rather than UTF-8,
# so any such print() crashes with UnicodeEncodeError the first time it runs
# — this used to take the whole app down at startup, and (worse) crashed
# add_cors_headers on every request while the DB was unreachable, since that
# handler's own failure-path print() carried the same emoji. Reconfiguring
# once, here, at the top of the entry module, fixes every print() in the
# process instead of hunting down each individual call site.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import (
    LOCAL_NETWORK_ORIGIN_REGEX,
    is_allowed_origin,
    local_network_origins_enabled,
    settings,
)
from app.services.schema_migrations import run_migrations
from app.routers import health, curriculum, exercises, progress, ai_chat, nvo, mobile_uploads, auth, plan, error_logs
from app.routers.bug_report import router as bug_report_router
from app.routers.feedback import router as feedback_router
from app.routers.companion_pairing import router as companion_pairing_router
from app.routers.analytics import router as analytics_router
from app.routers.classrooms import router as classrooms_router
from app.middleware.ip_rate_limiter import IPRateLimiterMiddleware
from app.services.media_tokens import verify_media_token
import app.models.curriculum  # noqa: ensure models are registered
import app.models.progress    # noqa: ensure models are registered
import app.models.user        # noqa: ensure models are registered
import app.models.companion   # noqa: ensure models are registered
import app.models.nvo_exam    # noqa: ensure models are registered
import app.models.event_log   # noqa: ensure models are registered
import app.models.classroom   # noqa: ensure models are registered
import app.models.mobile_channel  # noqa: ensure models are registered

# Sentry: opt-in via SENTRY_DSN. Deliberately skipped entirely rather than
# initialized with an empty DSN — that keeps "no DSN configured" and
# "Sentry is off" the same, unambiguous state, with zero SDK overhead for
# every deployment that hasn't set one up yet.
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Math Learning Platform API",
    description="AI-powered math learning platform for Bulgarian 5th-7th grade students",
    version="1.0.0",
)

_schema_ready = False
_schema_lock = threading.Lock()


def _ensure_schema() -> None:
    """Migrate the database to Alembic head once per process.

    Runs from the first request as well as from startup: a serverless runtime
    is not guaranteed to deliver ASGI startup events, and this used to call
    create_all() here — see schema_migrations.py for why that stopped being
    good enough. On failure the next request tries again, same as before.
    """
    global _schema_ready
    if _schema_ready or not settings.DB_AUTO_MIGRATE:
        return
    with _schema_lock:
        if _schema_ready:
            return
        try:
            revision = run_migrations()
            _schema_ready = True
            logger.info("Database schema at revision %s", revision)
        except Exception:
            logger.exception("Database migration failed; retrying on the next request")

# Unconditionally inject CORS headers on every response (including 500 errors).
# SECURITY: previously stamped "*" on every response. Now we reflect only the
# configured origins (never "*") and only when the request Origin is allow-listed,
# so untrusted sites cannot call the API with a victim's credentials.
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    _ensure_schema()
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin and is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Also keep CORSMiddleware so OPTIONS pre-flight works
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=LOCAL_NETWORK_ORIGIN_REGEX if local_network_origins_enabled() else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(IPRateLimiterMiddleware)

# Include routers
app.include_router(health.router)
app.include_router(curriculum.router)
app.include_router(exercises.router)
app.include_router(progress.router)
app.include_router(ai_chat.router)
app.include_router(nvo.router)
app.include_router(mobile_uploads.router)
app.include_router(auth.router)
app.include_router(plan.router)
app.include_router(error_logs.router)
app.include_router(bug_report_router)
app.include_router(feedback_router)
app.include_router(companion_pairing_router)
app.include_router(analytics_router)
app.include_router(classrooms_router)

MEDIA_DIR = Path(__file__).resolve().parent / "uploads"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/media/{filename}")
async def get_media(filename: str, token: str | None = None):
    """Serve an uploaded student photo, but only with a valid signed token.

    SECURITY: this used to be an unauthenticated StaticFiles mount, so every
    homework photo was world-readable forever to anyone holding (or guessing)
    a uuid4 filename. Tokens are HMAC-bound to the filename and expire.
    """
    # Reject traversal before touching the filesystem.
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name:
        raise HTTPException(status_code=404, detail="Not found")

    if not verify_media_token(safe_name, token):
        raise HTTPException(status_code=403, detail="Invalid or expired media link")

    file_path = MEDIA_DIR / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(file_path)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Math Learning Platform API...")
    print(f"📝 Environment: {settings.ENVIRONMENT}")
    _ensure_schema()
    print(f"🔗 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("👋 Shutting down Math Learning Platform API...")
