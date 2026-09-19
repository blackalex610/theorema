from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import json

from fastapi.responses import Response

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user, get_optional_user, require_admin, FREE_LIMITS
from app.services.guest_cleanup import purge_stale_guests
from app.services.user_data import delete_user_account, export_user_data

router = APIRouter(prefix="/auth", tags=["auth"])

# Per-IP guest account cap: past this many guest rows created from one IP in
# the window below, further guest creation is refused. This is the stateless
# backstop behind the in-memory IPRateLimiterMiddleware tier, which resets on
# every serverless cold start and is not sufficient alone.
GUEST_CAP_PER_IP = 10
GUEST_CAP_WINDOW_HOURS = 24


class GoogleToken(BaseModel):
    token: str


def _make_jwt(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expire, "typ": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _client_ip(request: Request) -> str | None:
    return (
        (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )


def _verify_google_token(raw_token: str) -> dict:
    """Verify a Google ID token and return its claims.

    Raises HTTPException(401) for an invalid/expired token and (502) for a
    verification-transport failure. Also enforces email_verified — Google can
    return an unverified email for some account types, and writing one into a
    unique-indexed column would let it permanently squat that address.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")
    try:
        info = id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google token") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Google token verification failed") from exc

    if info.get("email") and not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return info


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "plan": user.plan,
        "is_guest": user.is_guest,
    }


def _issue_session(user: User) -> dict:
    return {
        "access_token": _make_jwt(user.id),
        "token_type": "bearer",
        "user": _user_payload(user),
    }


@router.post("/google")
async def google_login(body: GoogleToken, request: Request, db: Session = Depends(get_db)):
    info = _verify_google_token(body.token)

    google_sub = info.get("sub")
    email = info.get("email") or None
    name = info.get("name", "")
    picture = info.get("picture", "")
    client_ip = _client_ip(request)

    try:
        user = db.query(User).filter(User.google_sub == google_sub).first()
        if not user and email:
            # Fall back to a verified-email match on a non-guest row and
            # backfill google_sub. Without this, a row that predates Google
            # sign-in (or was re-created with a different `sub`) collides on
            # the unique `email` index on the INSERT below and surfaces as a
            # misleading 503 "Database unavailable".
            existing = (
                db.query(User)
                .filter(User.email == email, User.is_guest.is_(False))
                .first()
            )
            if existing:
                existing.google_sub = google_sub
                user = existing

        if not user:
            user = User(
                google_sub=google_sub,
                email=email,
                name=name,
                picture=picture,
                last_login_ip=client_ip,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Sync latest profile info
            user.name = name
            user.picture = picture
            user.last_login_ip = client_ip
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return _issue_session(user)


@router.post("/guest")
async def guest_login(request: Request, db: Session = Depends(get_db)):
    """Create (or renew) a real, durable guest account.

    Returns the same payload shape as /auth/google so the frontend has one
    code path for both. A guest gets a real user_id and a normal JWT, so
    every DB-backed feature works identically to a signed-in user.
    """
    client_ip = _client_ip(request)

    # Every DB touch below (the reuse lookup, the per-IP count, and the
    # insert) needs the same 503 treatment on a database outage — this used
    # to only wrap the final insert, so a dead DB surfaced as a raw
    # framework 500 on the count query instead of the intended response.
    try:
        # Reuse before create: a caller that already holds a valid guest
        # token gets a fresh token for the SAME row instead of a new one.
        # This turns the dominant real-world case — a visitor reloading `/`
        # — from N rows into 1.
        existing_user = get_optional_user(
            authorization=request.headers.get("authorization"), db=db
        )
        if existing_user and existing_user.is_guest:
            return _issue_session(existing_user)

        if client_ip:
            window_start = datetime.now(timezone.utc) - timedelta(hours=GUEST_CAP_WINDOW_HOURS)
            recent_guests = (
                db.query(User)
                .filter(
                    User.is_guest.is_(True),
                    User.last_login_ip == client_ip,
                    User.created_at >= window_start,
                )
                .count()
            )
            if recent_guests >= GUEST_CAP_PER_IP:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "RATE_LIMITED",
                        "message": "Прекалено много гост профили от този адрес. Опитай по-късно.",
                    },
                )

        user = User(is_guest=True, name="Гост", plan="free", last_login_ip=client_ip)
        db.add(user)
        db.commit()
        db.refresh(user)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return _issue_session(user)


@router.post("/link-google")
async def link_google(
    body: GoogleToken,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upgrade the caller's guest account to a real Google account in place.

    The row's id never changes, so every table that references user_id keeps
    pointing at the same user with zero data migration. If the Google account
    is already linked to a different user, this refuses rather than merging
    two accounts' data — the caller should sign into that account instead.
    """
    if not current_user.is_guest:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_LINKED", "message": "Профилът вече е свързан."})

    info = _verify_google_token(body.token)
    google_sub = info.get("sub")
    email = info.get("email") or None

    try:
        conflict = db.query(User).filter(User.google_sub == google_sub).first()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ACCOUNT_EXISTS",
                    "message": "Вече има профил с този Google акаунт. Прогресът като гост няма да бъде прехвърлен.",
                    "access_token": _make_jwt(conflict.id),
                    "user": _user_payload(conflict),
                },
            )

        current_user.google_sub = google_sub
        current_user.email = email
        current_user.name = info.get("name", current_user.name)
        current_user.picture = info.get("picture", current_user.picture)
        current_user.is_guest = False
        current_user.upgraded_at = datetime.now(timezone.utc)
        current_user.last_login_ip = _client_ip(request)
        db.commit()
        db.refresh(current_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return _issue_session(current_user)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return current user info + plan status."""
    limits = FREE_LIMITS if current_user.plan == "free" else {k: 999_999 for k in FREE_LIMITS}
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
        "plan": current_user.plan,
        "is_guest": current_user.is_guest,
        "usage": {
            "ai_exercises": {"used": current_user.ai_exercises_today, "limit": limits["ai_exercises"]},
            "ai_chat": {"used": current_user.ai_chat_today, "limit": limits["ai_chat"]},
            "ai_theory": {"used": current_user.ai_theory_today, "limit": limits["ai_theory"]},
            "nvo_exams": {"used": current_user.nvo_exams_today, "limit": limits["nvo_exams"]},
        },
    }


@router.get("/me/export")
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR Art. 15/20: everything we hold about the caller, as a download.

    Served as an attachment rather than a JSON body so "get my data" produces
    a file the student or their parent can actually keep, which is what
    portability means.
    """
    payload = export_user_data(db, current_user)
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="smartnvo-danni-{current_user.id}.json"'
        },
    )


@router.delete("/me")
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GDPR Art. 17: erase the account and every row belonging to it.

    Irreversible and immediate — no soft-delete flag, because a "deleted"
    account that still holds a child's homework photos and answer history is
    not erasure. The JWT keeps its shape but stops resolving to anyone, so
    the caller's existing token is dead the moment this returns.
    """
    try:
        counts = delete_user_account(db, current_user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {"deleted": True, "removed_rows": counts}


@router.post("/admin/purge-guests")
async def purge_guests(
    older_than_days: int = 30,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete guest accounts older than `older_than_days` with zero activity.

    No scheduler wired up yet — call this manually or from an external cron
    hitting it with an admin token.
    """
    deleted = purge_stale_guests(db, older_than_days=older_than_days)
    return {"deleted": deleted}
