from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.database import engine, Base, ensure_user_usage_columns
from app.auth.dependencies import require_admin

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Math Learning Platform API",
        "version": "1.0.0",
    }


@router.post("/admin/migrate")
async def run_migrations(_admin=Depends(require_admin)):
    """Create all DB tables if they don't exist (idempotent). Call once after deploy.

    SECURITY: previously had NO authentication and returned raw exception
    strings (schema/connection leak). Now requires an admin role and never
    leaks internals.
    """
    try:
        Base.metadata.create_all(bind=engine)
        ensure_user_usage_columns()
        return {"status": "ok", "message": "Tables created / verified successfully"}
    except Exception:
        raise HTTPException(status_code=500, detail="Migration failed. Check server logs.")
