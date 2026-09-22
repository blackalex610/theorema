"""Everything the platform holds about one student: export it, or erase it.

GDPR Art. 15 (access), Art. 17 (erasure) and Art. 20 (portability) are not
optional for a product whose users are 11-14 year olds in the EU, and neither
existed before this module.

The awkward part is that no `user_id` column in this schema carries a foreign
key back to `users` — every model still says "Will link to User model later".
So `db.delete(user)` neither cascades nor errors; it silently orphans every
child row. Erasure is therefore written by hand here, driven by
USER_OWNED_TABLES, which is deliberately the *single* registry both this
module and guest_cleanup read. The previous arrangement — guest_cleanup
keeping its own private copy of the list — had already drifted: NvoAttempt
was added to the schema and never added to that list, so a guest whose only
activity was an exam attempt counted as "inactive" and got purged out from
under their own rows.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.classroom import Classroom, ClassroomAssignment, ClassroomMember
from app.models.curriculum import ExerciseAttempt
from app.models.event_log import EventLog
from app.models.nvo_exam import NvoAttempt, NvoAttemptItem
from app.models.school import School, SchoolMember
from app.models.progress import (
    LessonProgress,
    UserBadge,
    UserDailyMission,
    UserMissionExercise,
    UserProgress,
    UserXpProfile,
    XpEvent,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# Every table with a user_id column. Adding a user-owned table to the schema
# without adding it here means that table is neither exported nor erased —
# keep this list and the schema in lockstep (test_user_data.py pins it).
USER_OWNED_TABLES = (
    ExerciseAttempt,
    UserProgress,
    LessonProgress,
    UserXpProfile,
    XpEvent,
    UserBadge,
    UserDailyMission,
    NvoAttempt,
    # The per-question breakdown behind every teacher-facing diagnostic. It
    # carries its own user_id precisely so erasure reaches it: the FK to
    # nvo_attempts declares ON DELETE CASCADE, but nothing in this schema is
    # deleted by the database, so the cascade never fires.
    NvoAttemptItem,
)

# Which of those belong under "progress" in an export, for a shape a human
# can actually read rather than one flat dump.
_PROGRESS_TABLES = USER_OWNED_TABLES


def _as_jsonable(value: Any) -> Any:
    """datetime/date -> ISO string; everything else already serialises."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        column.name: _as_jsonable(getattr(row, column.name))
        for column in row.__table__.columns
    }


def _submitted_log_rows(db: Session, user_id: int) -> list[EventLog]:
    """event_logs rows this user submitted (bug reports, feedback, errors).

    user_id lives inside payload_json rather than in a column, and the
    frontend sends it as a string while users.id is an int — so narrow with
    a LIKE (cheap, index-free but selective) and confirm precisely in Python
    rather than reaching for dialect-specific JSON operators that would
    behave differently on SQLite and Postgres.
    """
    needle = f'"user_id": "{user_id}"'
    numeric_needle = f'"user_id": {user_id}'
    candidates = (
        db.query(EventLog)
        .filter(
            EventLog.payload_json.like(f"%{needle}%")
            | EventLog.payload_json.like(f"%{numeric_needle}%")
        )
        .all()
    )

    matched: list[EventLog] = []
    for row in candidates:
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            continue
        if str(payload.get("user_id")) == str(user_id):
            matched.append(row)
    return matched


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    """Everything held about `user`, as a JSON-serialisable dict.

    Deliberately includes the raw account row: a portability export that
    omits what the account itself knows about the person is not portability.
    """
    user_id = int(user.id)

    progress: dict[str, list[dict[str, Any]]] = {}
    for table in _PROGRESS_TABLES:
        rows = db.query(table).filter(table.user_id == user_id).all()
        progress[table.__tablename__] = [_row_to_dict(row) for row in rows]

    submitted_logs = [
        json.loads(row.payload_json) for row in _submitted_log_rows(db, user_id)
    ]

    taught = db.query(Classroom).filter(Classroom.teacher_id == user_id).all()
    joined = (
        db.query(Classroom)
        .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
        .filter(ClassroomMember.student_id == user_id)
        .all()
    )

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "account": _row_to_dict(user),
        "progress": progress,
        "submitted_logs": submitted_logs,
        "classrooms": {
            "taught": [_row_to_dict(c) for c in taught],
            "joined": [_row_to_dict(c) for c in joined],
        },
    }


def delete_user_account(db: Session, user: User) -> dict[str, int]:
    """Erase the account and every row belonging to it. Returns row counts.

    Order matters: user_mission_exercises hangs off user_daily_missions.id
    rather than carrying a user_id of its own, so it has to go before the
    missions it references.
    """
    user_id = int(user.id)
    counts: dict[str, int] = {}

    mission_ids = [
        row.id for row in
        db.query(UserDailyMission.id).filter(UserDailyMission.user_id == user_id).all()
    ]
    if mission_ids:
        counts["user_mission_exercises"] = (
            db.query(UserMissionExercise)
            .filter(UserMissionExercise.mission_id.in_(mission_ids))
            .delete(synchronize_session=False)
        )
    else:
        counts["user_mission_exercises"] = 0

    for table in USER_OWNED_TABLES:
        counts[table.__tablename__] = (
            db.query(table).filter(table.user_id == user_id).delete(synchronize_session=False)
        )

    # Classrooms key off teacher_id/student_id rather than a `user_id` column,
    # so they sit outside USER_OWNED_TABLES and are handled explicitly. A
    # deleted teacher must not leave a live join code and a roster of
    # children behind; a deleted student just leaves the classes they were in.
    taught_ids = [
        row.id for row in
        db.query(Classroom.id).filter(Classroom.teacher_id == user_id).all()
    ]
    assignments_removed = 0
    if taught_ids:
        db.query(ClassroomMember).filter(
            ClassroomMember.classroom_id.in_(taught_ids)
        ).delete(synchronize_session=False)
        # Assignments set in those classes go with them: homework pointing at
        # a class that no longer exists is orphaned data, and its rows name
        # the teacher who is being erased.
        assignments_removed += db.query(ClassroomAssignment).filter(
            ClassroomAssignment.classroom_id.in_(taught_ids)
        ).delete(synchronize_session=False)
    # Any left keyed to this teacher but sitting in someone else's class —
    # shouldn't happen, but erasure is not the place to assume that.
    assignments_removed += db.query(ClassroomAssignment).filter(
        ClassroomAssignment.teacher_id == user_id
    ).delete(synchronize_session=False)
    counts["classroom_assignments"] = assignments_removed

    # Schools, same shape one level up: a deleted director must not leave a
    # live join code that teachers can still walk into, and a deleted teacher
    # must not stay on a staff list.
    directed_ids = [
        row.id for row in
        db.query(School.id).filter(School.director_id == user_id).all()
    ]
    memberships_removed = 0
    if directed_ids:
        memberships_removed += db.query(SchoolMember).filter(
            SchoolMember.school_id.in_(directed_ids)
        ).delete(synchronize_session=False)
        # Classes attached to a school that is going away are released
        # rather than deleted: they belong to their teachers, who did not
        # ask to lose them because the director closed the account.
        db.query(Classroom).filter(Classroom.school_id.in_(directed_ids)).update(
            {Classroom.school_id: None}, synchronize_session=False
        )
    memberships_removed += db.query(SchoolMember).filter(
        SchoolMember.teacher_id == user_id
    ).delete(synchronize_session=False)
    counts["school_members"] = memberships_removed
    counts["schools"] = db.query(School).filter(
        School.director_id == user_id
    ).delete(synchronize_session=False)
    counts["classroom_members"] = db.query(ClassroomMember).filter(
        ClassroomMember.student_id == user_id
    ).delete(synchronize_session=False)
    counts["classrooms"] = db.query(Classroom).filter(
        Classroom.teacher_id == user_id
    ).delete(synchronize_session=False)

    log_rows = _submitted_log_rows(db, user_id)
    for row in log_rows:
        db.delete(row)
    counts["event_logs"] = len(log_rows)

    db.delete(user)
    db.commit()

    logger.info("Erased account %s: %s", user_id, counts)
    return counts
