"""What a director logs into — and the line they do not cross.

See models/school.py for why there is no role column and why the join code
is the consent record at this level too.

The design constraint that shapes every function here: **a director reads
cohort and class-level aggregates, never another teacher's individual
students.** An 11-year-old typed a code to become visible to one teacher.
Nothing in that act hands their record to the whole building. So the
overview counts, bands and topic percentages — and the roster stays exactly
where it was, behind "you read the classes you teach".

That is also the easier conversation to have with a school, and it costs
the product nothing a director actually needs: "which of my classes is
behind, and on what" is answerable without naming a child.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.classroom import Classroom, ClassroomMember
from app.models.nvo_exam import NvoAttempt
from app.models.school import School, SchoolMember
from app.models.user import User
from app.services.classroom_analytics import _strand_rows, _topic_rows, _rankable, RANKING_SIZE

# Same alphabet as class codes: read off a screen or a staff-room whiteboard
# and typed by hand, so no O/0 and no I/1/L.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
_MAX_CODE_ATTEMPTS = 10

#: Readiness bands for the latest score a student has. Chosen to line up with
#: how Bulgarian НВО results are talked about (a rough 2-6 scale), not with
#: round decimal numbers.
READINESS_BANDS: tuple[tuple[str, str, int], ...] = (
    ("excellent", "Отличен (85-100%)", 85),
    ("good", "Добър (60-84%)", 60),
    ("borderline", "Граничен (40-59%)", 40),
    ("at_risk", "В риск (под 40%)", 0),
)


def _generate_join_code(db: Session) -> str:
    for _ in range(_MAX_CODE_ATTEMPTS):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.query(School).filter(School.join_code == code).first():
            return code
    raise HTTPException(status_code=503, detail="Не може да се издаде код. Опитайте отново.")


# ─── Schools ─────────────────────────────────────────────────────────────────

def create_school(
    db: Session, *, director_id: int, name: str, city: str | None = None
) -> School:
    school = School(
        director_id=director_id,
        name=name.strip(),
        city=(city or "").strip() or None,
        join_code=_generate_join_code(db),
    )
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def _directed_school(db: Session, school_id: int, director_id: int) -> School:
    """A school the caller actually directs, or a 404 — matching the
    classroom rule that an id's existence is not probeable by a stranger."""
    school = (
        db.query(School)
        .filter(School.id == school_id, School.director_id == director_id)
        .one_or_none()
    )
    if school is None:
        raise HTTPException(status_code=404, detail="Училището не е намерено.")
    return school


def join_school(db: Session, *, teacher_id: int, join_code: str) -> School:
    """A teacher's own act of joining. The director cannot do this for them."""
    code = (join_code or "").strip().upper()
    school = db.query(School).filter(School.join_code == code).one_or_none()
    if school is None:
        raise HTTPException(status_code=404, detail="Няма училище с този код.")
    if not school.is_active:
        raise HTTPException(status_code=410, detail="Това училище вече не приема учители.")

    existing = (
        db.query(SchoolMember)
        .filter(
            SchoolMember.school_id == school.id, SchoolMember.teacher_id == teacher_id
        )
        .one_or_none()
    )
    if existing is None:
        db.add(SchoolMember(school_id=school.id, teacher_id=teacher_id))
        db.commit()
    return school


def list_schools_for_teacher(db: Session, *, teacher_id: int) -> list[School]:
    return (
        db.query(School)
        .join(SchoolMember, SchoolMember.school_id == School.id)
        .filter(SchoolMember.teacher_id == teacher_id)
        .order_by(School.created_at.desc())
        .all()
    )


def list_schools_for_director(db: Session, *, director_id: int) -> list[School]:
    return (
        db.query(School)
        .filter(School.director_id == director_id)
        .order_by(School.created_at.desc())
        .all()
    )


def _is_member(db: Session, school_id: int, teacher_id: int) -> bool:
    return (
        db.query(SchoolMember)
        .filter(SchoolMember.school_id == school_id, SchoolMember.teacher_id == teacher_id)
        .first()
        is not None
    )


# ─── Attaching a class (the teacher's decision) ──────────────────────────────

def attach_classroom(
    db: Session, *, school_id: int, classroom_id: int, teacher_id: int
) -> Classroom:
    """Link a class the caller teaches to a school the caller has joined.

    Both halves matter. Requiring ownership of the class is what stops a
    director sweeping other people's classes into a report; requiring
    membership of the school is what stops a class being attached to a
    building the teacher has nothing to do with.
    """
    classroom = (
        db.query(Classroom)
        .filter(Classroom.id == classroom_id, Classroom.teacher_id == teacher_id)
        .one_or_none()
    )
    if classroom is None:
        raise HTTPException(status_code=404, detail="Класът не е намерен.")

    school = db.query(School).filter(School.id == school_id).one_or_none()
    if school is None:
        raise HTTPException(status_code=404, detail="Училището не е намерено.")
    if school.director_id != teacher_id and not _is_member(db, school_id, teacher_id):
        raise HTTPException(
            status_code=403, detail="Не сте присъединен към това училище."
        )

    classroom.school_id = school_id
    db.commit()
    db.refresh(classroom)
    return classroom


def detach_classroom(db: Session, *, classroom_id: int, teacher_id: int) -> Classroom:
    """Withdrawing a class from a school. Needs no director involvement, for
    the same reason leaving a class needs no teacher involvement."""
    classroom = (
        db.query(Classroom)
        .filter(Classroom.id == classroom_id, Classroom.teacher_id == teacher_id)
        .one_or_none()
    )
    if classroom is None:
        raise HTTPException(status_code=404, detail="Класът не е намерен.")
    classroom.school_id = None
    db.commit()
    db.refresh(classroom)
    return classroom


# ─── The director's overview ─────────────────────────────────────────────────

def _latest_score_per_student(db: Session, student_ids: list[int]) -> dict[int, int]:
    """Each student's most recent graded percentage.

    Latest rather than average on purpose: readiness is a question about
    where a cohort is *now*, and an average drags a student who has improved
    all term back towards where they started.
    """
    if not student_ids:
        return {}

    latest = (
        db.query(
            NvoAttempt.user_id.label("user_id"),
            func.max(NvoAttempt.created_at).label("created_at"),
        )
        .filter(NvoAttempt.user_id.in_(student_ids))
        .group_by(NvoAttempt.user_id)
        .subquery()
    )
    rows = (
        db.query(NvoAttempt.user_id, NvoAttempt.percentage_correct)
        .join(
            latest,
            (NvoAttempt.user_id == latest.c.user_id)
            & (NvoAttempt.created_at == latest.c.created_at),
        )
        .all()
    )
    return {row.user_id: int(row.percentage_correct or 0) for row in rows}


def _readiness(scores: dict[int, int]) -> list[dict[str, Any]]:
    counts = {key: 0 for key, _label, _floor in READINESS_BANDS}
    for score in scores.values():
        for key, _label, floor in READINESS_BANDS:
            if score >= floor:
                counts[key] += 1
                break
    return [
        {"key": key, "label": label, "students": counts[key]}
        for key, label, _floor in READINESS_BANDS
    ]


def build_school_overview(
    db: Session, *, school_id: int, director_id: int
) -> dict[str, Any]:
    """Cohort-level picture of a school, for the director who created it.

    Carries no student identity by construction: every figure below is a
    count, a band or a percentage over a group. See the module docstring.
    """
    school = _directed_school(db, school_id, director_id)

    classrooms = (
        db.query(Classroom)
        .filter(Classroom.school_id == school_id)
        .order_by(Classroom.grade_level, Classroom.name)
        .all()
    )
    classroom_ids = [c.id for c in classrooms]

    members: list[ClassroomMember] = []
    if classroom_ids:
        members = (
            db.query(ClassroomMember)
            .filter(ClassroomMember.classroom_id.in_(classroom_ids))
            .all()
        )
    students_by_class: dict[int, list[int]] = {}
    for member in members:
        students_by_class.setdefault(member.classroom_id, []).append(member.student_id)

    # A teacher with two classes is one seat-payer but one teacher; a student
    # in two of this school's classes is one child, counted once.
    all_student_ids = sorted({m.student_id for m in members})
    scores = _latest_score_per_student(db, all_student_ids)

    teacher_ids = {c.teacher_id for c in classrooms}
    teacher_ids |= {
        row.teacher_id
        for row in db.query(SchoolMember.teacher_id)
        .filter(SchoolMember.school_id == school_id)
        .all()
    }
    teacher_names = {
        u.id: (u.name or "Учител")
        for u in db.query(User).filter(User.id.in_(list(teacher_ids) or [0])).all()
    }

    class_rows: list[dict[str, Any]] = []
    for classroom in classrooms:
        ids = students_by_class.get(classroom.id, [])
        class_scores = [scores[sid] for sid in ids if sid in scores]
        class_rows.append(
            {
                "classroom_id": classroom.id,
                "name": classroom.name,
                "grade_level": classroom.grade_level,
                "teacher_name": teacher_names.get(classroom.teacher_id, "Учител"),
                # A count, never a list: the director gets the size of the
                # class, not who is in it.
                "students": len(ids),
                "students_with_data": len(class_scores),
                "average_latest_score": (
                    round(sum(class_scores) / len(class_scores)) if class_scores else None
                ),
            }
        )

    grades: dict[int | None, dict[str, Any]] = {}
    for row in class_rows:
        bucket = grades.setdefault(
            row["grade_level"], {"grade_level": row["grade_level"], "classes": 0, "students": 0}
        )
        bucket["classes"] += 1
        bucket["students"] += row["students"]

    topics = _topic_rows(db, all_student_ids)

    return {
        "id": school.id,
        "name": school.name,
        "city": school.city,
        "join_code": school.join_code,
        "created_at": school.created_at.isoformat(),
        "class_count": len(classrooms),
        "teacher_count": len(teacher_ids),
        # What a licence would be counted in. Distinct children, so a student
        # in two of this school's classes is one seat.
        "seats_used": len(all_student_ids),
        "students_with_data": len(scores),
        "classes": class_rows,
        "grades": sorted(
            grades.values(), key=lambda g: (g["grade_level"] is None, g["grade_level"])
        ),
        "readiness": _readiness(scores),
        "topics": topics,
        "strands": _strand_rows(topics),
        "weakest": _rankable(topics)[:RANKING_SIZE],
    }
