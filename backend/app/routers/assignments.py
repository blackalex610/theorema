"""Setting homework, and reading back what came in.

The audit's T5 — "nothing to hand in, nothing to hand back" — starts here:
a class code and a roster are not an assignment. See
models/classroom.py::ClassroomAssignment for why the whole class sits one
pinned paper, and services/assignment_service for the two mechanics that
carry the feature (the paper outliving its 24h TTL, and the student's daily
exam quota not being charged for homework the teacher already paid to
generate).

Routes live under their own /assignments prefix rather than nested under
/classrooms/{id} so that the student-facing ones — who has no class id to
hand — are not forced through a path segment they cannot fill.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, increment_usage, require_nvo_exam_capacity
from app.database import get_db
from app.models.user import User
from app.services import assignment_service as svc

router = APIRouter(prefix="/assignments", tags=["assignments"])


class CreateAssignmentRequest(BaseModel):
    classroom_id: int
    title: str = Field(..., min_length=1, max_length=160)
    due_at: datetime | None = None
    difficulty: str | None = None
    format: str | None = None
    blueprint: str | None = None

    @field_validator("title")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Заданието трябва да има заглавие.")
        return value


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_assignment(
    payload: CreateAssignmentRequest,
    current_user: User = Depends(require_nvo_exam_capacity),
    db: Session = Depends(get_db),
):
    """Generate one paper and pin it to a class.

    The teacher's own daily exam credit is charged, and only after the paper
    exists — this generates a real exam, and the audit's I4 finding (free,
    unbounded generation against a price nobody has set) applies to teachers
    as much as students. Their students are not charged for sitting it.
    """
    # Built through the same ladder as POST /nvo/generate, deliberately: a
    # second copy of the fallback chain would drift from the first.
    from app.routers.nvo import _store_exam, generate_exam_paper

    exam = generate_exam_paper(payload.blueprint, payload.difficulty, payload.format)
    _store_exam(exam)

    assignment = svc.create_assignment(
        db,
        classroom_id=payload.classroom_id,
        teacher_id=int(current_user.id),
        title=payload.title,
        exam_id=exam.exam_id,
        due_at=payload.due_at,
        difficulty=exam.difficulty,
        format_=exam.format,
        blueprint=payload.blueprint,
    )
    increment_usage(current_user, db, "nvo_exams")
    return svc.build_assignment_report(
        db, assignment_id=assignment.id, teacher_id=int(current_user.id)
    )


@router.get("/mine")
async def list_my_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Homework, as a student sees it.

    Declared before /{assignment_id} so the path converter cannot try to
    read "mine" as an id.
    """
    return {"assignments": svc.list_assignments_for_student(db, student_id=int(current_user.id))}


@router.get("/class/{classroom_id}")
async def list_class_assignments(
    classroom_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {
        "assignments": svc.list_assignments_for_class(
            db, classroom_id=classroom_id, teacher_id=int(current_user.id)
        )
    }


@router.get("/{assignment_id}")
async def get_assignment_report(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Who handed in, how they did, and which questions the class fell over
    on — the last of which is only a sentence because everyone sat one paper."""
    return svc.build_assignment_report(
        db, assignment_id=assignment_id, teacher_id=int(current_user.id)
    )


@router.post("/{assignment_id}/open")
async def open_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hand the student the pinned paper.

    Deliberately NOT behind require_nvo_exam_capacity and deliberately not
    calling increment_usage: no generation happens here, the teacher already
    spent a credit producing this paper, and a student locked out of their
    own homework by the free tier's one-exam-a-day quota would be the
    product's worst moment. The answer key is stripped as on every other
    client-facing exam route.
    """
    from app.routers.nvo import _load_exam, _strip_answer_key

    exam_id = svc.exam_id_for_student(
        db, assignment_id=assignment_id, student_id=int(current_user.id)
    )
    exam = _load_exam(exam_id)
    if not exam:
        # The pin should prevent this; if it happens the paper was purged or
        # never stored, and saying so beats handing back an empty exam.
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Изпитният вариант не е наличен.")
    return _strip_answer_key(exam)


@router.post("/{assignment_id}/close")
async def close_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.close_assignment(db, assignment_id=assignment_id, teacher_id=int(current_user.id))
    return svc.build_assignment_report(
        db, assignment_id=assignment_id, teacher_id=int(current_user.id)
    )


@router.post("/{assignment_id}/reopen")
async def reopen_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.reopen_assignment(db, assignment_id=assignment_id, teacher_id=int(current_user.id))
    return svc.build_assignment_report(
        db, assignment_id=assignment_id, teacher_id=int(current_user.id)
    )
