"""Classroom membership and the roster a teacher actually looks at.

See app/models/classroom.py for why teacher-ness is not a role flag and why
the join code is treated as the consent record.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.classroom import Classroom, ClassroomMember
from app.models.nvo_exam import NvoAttempt
from app.models.progress import UserXpProfile
from app.models.user import User
from app.services.progress_service import ProgressService

# A code gets read off a whiteboard and typed by a 12-year-old, so the
# alphabet drops every pair that gets misread by hand or by eye: O/0, I/1/L.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6
_MAX_CODE_ATTEMPTS = 10


def _generate_join_code(db: Session) -> str:
    for _ in range(_MAX_CODE_ATTEMPTS):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        if not db.query(Classroom).filter(Classroom.join_code == code).first():
            return code
    # 31^6 is ~887 million; ten collisions in a row means something is very
    # wrong, and silently handing back a duplicate would be worse.
    raise HTTPException(status_code=503, detail="Could not allocate a class code. Try again.")


# ─── Classes ─────────────────────────────────────────────────────────────────

def create_classroom(
    db: Session, *, teacher_id: int, name: str, grade_level: int | None = None
) -> Classroom:
    classroom = Classroom(
        teacher_id=teacher_id,
        name=name.strip(),
        join_code=_generate_join_code(db),
        grade_level=grade_level,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


def list_classrooms_for_teacher(db: Session, teacher_id: int) -> list[Classroom]:
    return (
        db.query(Classroom)
        .filter(Classroom.teacher_id == teacher_id)
        .order_by(Classroom.created_at.desc())
        .all()
    )


def list_classrooms_for_student(db: Session, student_id: int) -> list[Classroom]:
    return (
        db.query(Classroom)
        .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
        .filter(ClassroomMember.student_id == student_id)
        .order_by(Classroom.created_at.desc())
        .all()
    )


def _owned_classroom(db: Session, classroom_id: int, teacher_id: int) -> Classroom:
    """A class the caller actually teaches, or a 404.

    404 rather than 403 on purpose: whether a given class id exists is not
    something a stranger should be able to probe for.
    """
    classroom = (
        db.query(Classroom)
        .filter(Classroom.id == classroom_id, Classroom.teacher_id == teacher_id)
        .one_or_none()
    )
    if classroom is None:
        raise HTTPException(status_code=404, detail="Класът не е намерен.")
    return classroom


def archive_classroom(db: Session, *, classroom_id: int, teacher_id: int) -> Classroom:
    classroom = _owned_classroom(db, classroom_id, teacher_id)
    classroom.is_active = False
    db.commit()
    db.refresh(classroom)
    return classroom


# ─── Membership ──────────────────────────────────────────────────────────────

def join_classroom(db: Session, *, student_id: int, join_code: str) -> Classroom:
    code = (join_code or "").strip().upper()
    classroom = db.query(Classroom).filter(Classroom.join_code == code).one_or_none()
    if classroom is None:
        raise HTTPException(status_code=404, detail="Няма клас с този код.")
    if not classroom.is_active:
        raise HTTPException(status_code=410, detail="Този клас вече не приема нови ученици.")
    if classroom.teacher_id == student_id:
        raise HTTPException(
            status_code=400, detail="Не можеш да се присъединиш към собствения си клас."
        )

    existing = (
        db.query(ClassroomMember)
        .filter(
            ClassroomMember.classroom_id == classroom.id,
            ClassroomMember.student_id == student_id,
        )
        .one_or_none()
    )
    if existing is None:
        db.add(ClassroomMember(classroom_id=classroom.id, student_id=student_id))
        try:
            db.commit()
        except IntegrityError:
            # Two tabs racing the same code: the unique constraint is the
            # source of truth, and already-joined is the desired end state.
            db.rollback()

    return classroom


def list_members(db: Session, classroom_id: int) -> list[ClassroomMember]:
    return (
        db.query(ClassroomMember)
        .filter(ClassroomMember.classroom_id == classroom_id)
        .order_by(ClassroomMember.joined_at)
        .all()
    )


def remove_member(db: Session, *, classroom_id: int, teacher_id: int, student_id: int) -> None:
    _owned_classroom(db, classroom_id, teacher_id)
    db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == classroom_id,
        ClassroomMember.student_id == student_id,
    ).delete(synchronize_session=False)
    db.commit()


def leave_classroom(db: Session, *, classroom_id: int, student_id: int) -> None:
    """A student withdrawing their own consent. Deliberately needs no
    teacher involvement — opting out must be as easy as opting in."""
    db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == classroom_id,
        ClassroomMember.student_id == student_id,
    ).delete(synchronize_session=False)
    db.commit()


# ─── The roster ──────────────────────────────────────────────────────────────

def build_roster(db: Session, *, classroom_id: int, teacher_id: int) -> list[dict[str, Any]]:
    """One row per student, with progress the server actually computed.

    Every number here comes from server-side records — XP from the profile,
    exam scores from nvo_attempts, which /nvo/submit writes after grading all
    23 questions itself. Before that existed, a "class progress" view would
    have been a table of numbers the students' own browsers chose.

    Queried in bulk rather than per student: a class is 25-30 rows and a
    per-student query loop would be an N+1 on the one page a teacher opens
    most.
    """
    _owned_classroom(db, classroom_id, teacher_id)

    members = list_members(db, classroom_id)
    student_ids = [m.student_id for m in members]
    if not student_ids:
        return []

    users = {
        u.id: u for u in db.query(User).filter(User.id.in_(student_ids)).all()
    }
    profiles = {
        p.user_id: p
        for p in db.query(UserXpProfile).filter(UserXpProfile.user_id.in_(student_ids)).all()
    }

    exam_stats = {
        row.user_id: row
        for row in (
            db.query(
                NvoAttempt.user_id.label("user_id"),
                func.count(NvoAttempt.id).label("attempts"),
                func.avg(NvoAttempt.percentage_correct).label("avg_score"),
                func.max(NvoAttempt.percentage_correct).label("best_score"),
                func.max(NvoAttempt.created_at).label("last_attempt_at"),
            )
            .filter(NvoAttempt.user_id.in_(student_ids))
            .group_by(NvoAttempt.user_id)
            .all()
        )
    }

    service = ProgressService(db)
    roster: list[dict[str, Any]] = []
    for member in members:
        sid = member.student_id
        user = users.get(sid)
        profile = profiles.get(sid)
        stats = exam_stats.get(sid)
        total_xp = int(getattr(profile, "total_xp", 0) or 0)

        roster.append({
            "student_id": sid,
            "name": getattr(user, "name", None) or "Ученик",
            "is_guest": bool(getattr(user, "is_guest", False)),
            "joined_at": member.joined_at.isoformat(),
            "total_xp": total_xp,
            "level": service._get_level_info(total_xp)["level"],
            "streak_days": int(getattr(profile, "streak_days", 0) or 0),
            "exams_taken": int(stats.attempts) if stats else 0,
            "average_exam_score": round(float(stats.avg_score)) if stats and stats.avg_score is not None else None,
            "best_exam_score": int(stats.best_score) if stats and stats.best_score is not None else None,
            "last_exam_at": stats.last_attempt_at.isoformat() if stats and stats.last_attempt_at else None,
        })

    return roster
