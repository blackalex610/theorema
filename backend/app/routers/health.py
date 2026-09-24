import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.dependencies import require_admin
from app.database import engine
from app.services import schema_migrations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Liveness: the process is up. Touches nothing else, so it stays cheap."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Math Learning Platform API",
        "version": "1.0.0",
    }


def _readiness() -> tuple[int, dict]:
    head = schema_migrations.head_revision()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            current = schema_migrations.current_revision(conn)
    except Exception:
        logger.exception("Readiness check could not reach the database")
        return 503, {"status": "unavailable", "database": "unreachable"}

    migrated = current == head
    return (200 if migrated else 503), {
        "status": "ready" if migrated else "schema_behind",
        "database": "ok",
        "schema_revision": current,
        "schema_head": head,
    }


@router.get("/health/ready")
async def readiness_check():
    """Readiness: the database answers and its schema is at Alembic head.

    Point an uptime monitor here rather than at /health — a deploy whose
    database is down or unmigrated still reports "healthy" there.
    """
    status_code, body = await run_in_threadpool(_readiness)
    return JSONResponse(status_code=status_code, content=body)


@router.post("/admin/migrate")
async def run_migrations(_admin=Depends(require_admin)):
    """Upgrade the database to Alembic head (idempotent).

    The app already does this on its first request (see main._ensure_schema);
    this exists for DB_AUTO_MIGRATE=false deployments and for re-running
    after a failure without waiting for traffic.

    SECURITY: previously had NO authentication and returned raw exception
    strings (schema/connection leak). Now requires an admin role and never
    leaks internals.
    """
    try:
        revision = await run_in_threadpool(schema_migrations.run_migrations)
    except Exception:
        logger.exception("Admin-triggered migration failed")
        raise HTTPException(status_code=500, detail="Migration failed. Check server logs.")
    return {"status": "ok", "revision": revision}
