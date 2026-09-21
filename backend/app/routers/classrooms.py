"""Teacher and student views of a classroom.

The audit's T1 ("there is no teacher product — not partial, absent") and P4
("there is no parent in the product either") both come down to this: no adult
could see a student's work. These routes are that link.

Nothing here needs a `role`: you teach the classes you created and attend the
ones you joined. Reading a roster requires owning the class, and a class you
do not own answers 404 rather than 403 — whether a class id exists is not
something a stranger should be able to probe.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.classroom import Classroom
from app.models.user import User
from app.services import classroom_service as svc

router = APIRouter(prefix="/classrooms", tags=["classrooms"])


class CreateClassroomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    grade_level: int | None = Field(default=None, ge=5, le=7)

    @field_validator("name")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Класът трябва да има име.")
        return value


class JoinClassroomRequest(BaseModel):
    join_code: str = Field(..., min_length=4, max_length=12)


def _classroom_payload(db: Session, classroom: Classroom) -> dict:
    return {
        "id": classroom.id,
        "name": classroom.name,
        "join_code": classroom.join_code,
        "grade_level": classroom.grade_level,
        "is_active": classroom.is_active,
        "created_at": classroom.created_at.isoformat(),
        "student_count": len(svc.list_members(db, classroom.id)),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_classroom(
    payload: CreateClassroomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    classroom = svc.create_classroom(
        db, teacher_id=int(current_user.id), name=payload.name, grade_level=payload.grade_level
    )
    return _classroom_payload(db, classroom)


@router.get("")
async def list_my_classrooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Classes the caller teaches."""
    classrooms = svc.list_classrooms_for_teacher(db, int(current_user.id))
    return {"classrooms": [_classroom_payload(db, c) for c in classrooms]}


@router.get("/mine")
async def list_classrooms_i_joined(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Classes the caller joined as a student.

    Declared before /{classroom_id} on purpose: "mine" would otherwise be
    matched as a class id by the path converter.
    """
    classrooms = svc.list_classrooms_for_student(db, int(current_user.id))
    return {
        "classrooms": [
            {
                "id": c.id,
                "name": c.name,
                "grade_level": c.grade_level,
                "is_active": c.is_active,
            }
            for c in classrooms
        ]
    }


@router.post("/join")
async def join_classroom(
    payload: JoinClassroomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The student's own act of consent to be visible to this teacher."""
    classroom = svc.join_classroom(
        db, student_id=int(current_user.id), join_code=payload.join_code
    )
    return {"id": classroom.id, "name": classroom.name, "grade_level": classroom.grade_level}


@router.get("/{classroom_id}")
async def get_classroom_roster(
    classroom_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roster = svc.build_roster(db, classroom_id=classroom_id, teacher_id=int(current_user.id))
    classroom = svc._owned_classroom(db, classroom_id, int(current_user.id))
    return {**_classroom_payload(db, classroom), "roster": roster}


@router.post("/{classroom_id}/archive")
async def archive_classroom(
    classroom_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    classroom = svc.archive_classroom(
        db, classroom_id=classroom_id, teacher_id=int(current_user.id)
    )
    return _classroom_payload(db, classroom)


@router.delete("/{classroom_id}/members/{student_id}")
async def remove_student(
    classroom_id: int,
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.remove_member(
        db, classroom_id=classroom_id, teacher_id=int(current_user.id), student_id=student_id
    )
    return {"removed": True}


@router.delete("/{classroom_id}/leave")
async def leave_classroom(
    classroom_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdrawing consent. Needs no teacher involvement by design."""
    svc.leave_classroom(db, classroom_id=classroom_id, student_id=int(current_user.id))
    return {"left": True}
