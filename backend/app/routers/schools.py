"""The school layer: what a director opens.

See models/school.py and services/school_service for the design. The one
thing worth restating at the route level: there is no endpoint here that
returns an individual student. A director gets counts, bands and
percentages; the roster stays behind "you read the classes you teach".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import school_service as svc

router = APIRouter(prefix="/schools", tags=["schools"])


class CreateSchoolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    city: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Училището трябва да има име.")
        return value


class JoinSchoolRequest(BaseModel):
    join_code: str = Field(..., min_length=4, max_length=12)


class AttachClassroomRequest(BaseModel):
    classroom_id: int


def _school_payload(school) -> dict:
    return {
        "id": school.id,
        "name": school.name,
        "city": school.city,
        "join_code": school.join_code,
        "is_active": school.is_active,
        "created_at": school.created_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: CreateSchoolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    school = svc.create_school(
        db, director_id=int(current_user.id), name=payload.name, city=payload.city
    )
    return _school_payload(school)


@router.get("")
async def list_schools_i_direct(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schools = svc.list_schools_for_director(db, director_id=int(current_user.id))
    return {"schools": [_school_payload(s) for s in schools]}


@router.get("/mine")
async def list_schools_i_joined(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Schools the caller teaches in.

    Declared before /{school_id} so the path converter cannot read "mine"
    as an id — the same ordering the classrooms router needs.
    """
    schools = svc.list_schools_for_teacher(db, teacher_id=int(current_user.id))
    return {
        "schools": [
            {"id": s.id, "name": s.name, "city": s.city, "is_active": s.is_active}
            for s in schools
        ]
    }


@router.post("/join")
async def join_school(
    payload: JoinSchoolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The teacher's own act of joining. A director cannot do this for them."""
    school = svc.join_school(
        db, teacher_id=int(current_user.id), join_code=payload.join_code
    )
    return {"id": school.id, "name": school.name, "city": school.city}


@router.post("/{school_id}/classrooms")
async def attach_classroom(
    school_id: int,
    payload: AttachClassroomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach a class the caller teaches to a school the caller has joined.

    Both checks are the point: the director cannot sweep other people's
    classes into their report, and a class cannot be attached to a building
    its teacher has nothing to do with.
    """
    classroom = svc.attach_classroom(
        db,
        school_id=school_id,
        classroom_id=payload.classroom_id,
        teacher_id=int(current_user.id),
    )
    return {"classroom_id": classroom.id, "school_id": classroom.school_id}


@router.delete("/classrooms/{classroom_id}")
async def detach_classroom(
    classroom_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdrawing a class from a school — no director involvement, for the
    same reason a student leaving a class needs no teacher."""
    classroom = svc.detach_classroom(
        db, classroom_id=classroom_id, teacher_id=int(current_user.id)
    )
    return {"classroom_id": classroom.id, "school_id": classroom.school_id}


@router.get("/{school_id}")
async def get_school_overview(
    school_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cohort readiness, class-level averages, seats and topic weaknesses.

    Contains no student identity by construction — see school_service.
    """
    return svc.build_school_overview(
        db, school_id=school_id, director_id=int(current_user.id)
    )
