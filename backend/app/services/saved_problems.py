"""Saving, listing and removing a student's bookmarked problems.

Ownership is enforced here rather than in the router: every function takes an
explicit user_id and scopes on it, and a row belonging to someone else is a 404
rather than a 403 so that ids cannot be probed.
"""
from __future__ import annotations

import json

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.saved_problem import SavedProblem

SAVED_PROBLEMS_MAX_PER_USER = 200
SAVED_PROBLEMS_DEFAULT_LIMIT = 20
SAVED_PROBLEMS_MAX_LIMIT = 100

VALID_SOURCES = ("exercise", "nvo")

_MAX_SOURCE_REF_LENGTH = 128


def ref_key(source: str, source_ref: str) -> str:
    """The key the frontend uses to look a saved problem up."""
    return f"{source}:{source_ref}"


def snapshot_of(row: SavedProblem) -> dict:
    """Parse a stored snapshot, tolerating a corrupted one rather than 500ing."""
    try:
        parsed = json.loads(row.snapshot_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _validate(source: str, source_ref: str, snapshot: dict) -> None:
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail="Непознат тип задача.")
    if not source_ref or len(source_ref) > _MAX_SOURCE_REF_LENGTH:
        raise HTTPException(status_code=400, detail="Невалиден идентификатор на задача.")
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=400, detail="Невалидни данни за задачата.")
    question = snapshot.get("question")
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="Задачата няма условие.")


def _find(db: Session, *, user_id: int, source: str, source_ref: str) -> SavedProblem | None:
    return (
        db.query(SavedProblem)
        .filter(
            SavedProblem.user_id == user_id,
            SavedProblem.source == source,
            SavedProblem.source_ref == source_ref,
        )
        .first()
    )


def save_problem(
    db: Session, *, user_id: int, source: str, source_ref: str, snapshot: dict
) -> tuple[SavedProblem, bool]:
    """Save one problem. Returns (row, created).

    Idempotent: re-saving something already saved returns the existing row with
    created=False instead of raising. The bookmark button is a toggle and
    double-clicks are routine, so a duplicate must not be an error.
    """
    _validate(source, source_ref, snapshot)

    existing = _find(db, user_id=user_id, source=source, source_ref=source_ref)
    if existing is not None:
        return existing, False

    # Checked only for genuinely new rows, so someone at the cap can still
    # toggle problems they already saved.
    total = db.query(SavedProblem).filter(SavedProblem.user_id == user_id).count()
    if total >= SAVED_PROBLEMS_MAX_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Достигна максимума от {SAVED_PROBLEMS_MAX_PER_USER} запазени задачи. "
                "Премахни някои, за да запазиш нови."
            ),
        )

    row = SavedProblem(
        user_id=user_id,
        source=source,
        source_ref=source_ref,
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent saves of the same problem raced past the _find above.
        db.rollback()
        raced = _find(db, user_id=user_id, source=source, source_ref=source_ref)
        if raced is None:
            raise
        return raced, False
    db.refresh(row)
    return row, True


def list_problems(
    db: Session, *, user_id: int, limit: int, source: str | None = None
) -> list[SavedProblem]:
    """SECURITY: always scoped on the caller's own user_id."""
    query = db.query(SavedProblem).filter(SavedProblem.user_id == user_id)
    if source:
        if source not in VALID_SOURCES:
            raise HTTPException(status_code=400, detail="Непознат тип задача.")
        query = query.filter(SavedProblem.source == source)
    safe_limit = max(1, min(int(limit), SAVED_PROBLEMS_MAX_LIMIT))
    return (
        query.order_by(SavedProblem.created_at.desc(), SavedProblem.id.desc())
        .limit(safe_limit)
        .all()
    )


def list_refs(db: Session, *, user_id: int) -> dict[str, int]:
    """Every saved problem the user owns, as ref key -> row id.

    Returns the id so that un-saving needs no second round trip: a bookmark
    button knows (source, source_ref) but DELETE is keyed by id.
    """
    rows = (
        db.query(SavedProblem.id, SavedProblem.source, SavedProblem.source_ref)
        .filter(SavedProblem.user_id == user_id)
        .all()
    )
    return {ref_key(row.source, row.source_ref): row.id for row in rows}


def delete_problem(db: Session, *, user_id: int, saved_id: int) -> None:
    """SECURITY: 404 rather than 403 for someone else's row, so ids cannot be probed."""
    row = (
        db.query(SavedProblem)
        .filter(SavedProblem.id == saved_id, SavedProblem.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Задачата не е намерена.")
    db.delete(row)
    db.commit()
