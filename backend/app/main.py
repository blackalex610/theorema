from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.database import engine, Base, ensure_user_usage_columns
from app.routers import health, curriculum, exercises, progress, ai_chat, nvo, mobile_uploads, auth, plan, error_logs
from app.routers.bug_report import router as bug_report_router
from app.routers.feedback import router as feedback_router
from app.routers.companion_pairing import router as companion_pairing_router
from app.routers.analytics import router as analytics_router
from app.middleware.ip_rate_limiter import IPRateLimiterMiddleware
import app.models.curriculum  # noqa: ensure models are registered
import app.models.progress    # noqa: ensure models are registered
import app.models.user        # noqa: ensure models are registered
import app.models.companion   # noqa: ensure models are registered

app = FastAPI(
    title="Math Learning Platform API",
    description="AI-powered math learning platform for Bulgarian 5th-7th grade students",
    version="1.0.0",
)

_db_initialized = False

def _ensure_db_tables() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    global _db_initialized
    if _db_initialized:
        return
    try:
        Base.metadata.create_all(bind=engine)
        ensure_user_usage_columns()
        _db_initialized = True
        print("✅ DB tables verified/created")
    except Exception as exc:
        print(f"⚠️  DB create_all failed: {exc}")

# Unconditionally inject CORS headers on every response (including 500 errors).
# SECURITY: previously stamped "*" on every response. Now we reflect only the
# configured origins (never "*") and only when the request Origin is allow-listed,
# so untrusted sites cannot call the API with a victim's credentials.
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    _ensure_db_tables()
    response = await call_next(request)
    origin = request.headers.get("origin")
    allowed = settings.CORS_ORIGINS
    if origin and origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Also keep CORSMiddleware so OPTIONS pre-flight works
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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

MEDIA_DIR = Path(__file__).resolve().parent / "uploads"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Math Learning Platform API...")
    print(f"📝 Environment: {settings.ENVIRONMENT}")
    _ensure_db_tables()
    print(f"🔗 Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    print("👋 Shutting down Math Learning Platform API...")
