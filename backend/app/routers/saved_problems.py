"""Endpoints for a student's bookmarked problems.

Thin over app.services.saved_problems: validation, the cap and ownership all
live in the service. Every route is scoped on the authenticated caller.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import saved_problems as svc

router = APIRouter(prefix="/saved-problems", tags=["saved-problems"])


class SavedProblemCreate(BaseModel):
    source: str = Field(..., min_length=1, max_length=16)
    source_ref: str = Field(..., min_length=1, max_length=128)
    snapshot: dict


class SavedProblemOut(BaseModel):
    id: int
    source: str
    source_ref: str
    snapshot: dict
    created_at: str


class SavedRefsOut(BaseModel):
    refs: Dict[str, int]


def _to_out(row) -> SavedProblemOut:
    return SavedProblemOut(
        id=row.id,
        source=row.source,
        source_ref=row.source_ref,
        snapshot=svc.snapshot_of(row),
        created_at=row.created_at.isoformat(),
    )


@router.post("", response_model=SavedProblemOut, status_code=status.HTTP_201_CREATED)
async def create_saved_problem(
    payload: SavedProblemCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a problem. Returns 200 instead of 201 when it was already saved."""
    row, created = svc.save_problem(
        db,
        user_id=current_user.id,
        source=payload.source,
        source_ref=payload.source_ref,
        snapshot=payload.snapshot,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return _to_out(row)


@router.get("", response_model=List[SavedProblemOut])
async def list_saved_problems(
    limit: int = svc.SAVED_PROBLEMS_DEFAULT_LIMIT,
    source: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SECURITY: scoped on current_user.id; never accepts a caller-supplied user id."""
    rows = svc.list_problems(db, user_id=current_user.id, limit=limit, source=source)
    return [_to_out(row) for row in rows]


@router.get("/refs", response_model=SavedRefsOut)
async def list_saved_refs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ref key -> row id, so bookmark buttons can render their state from one call."""
    return SavedRefsOut(refs=svc.list_refs(db, user_id=current_user.id))


@router.delete("/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_problem(
    saved_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.delete_problem(db, user_id=current_user.id, saved_id=saved_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
