"""GDPR Art. 15/17/20: a student can get everything we hold and can erase it.

The product is aimed at 11-14 year olds in the EU and had no deletion path,
no export path, and no inventory of what it even stores per user. Worse, the
`user_id` columns carry no foreign key back to `users` (see the "Will link to
User model later" comments in the models), so deleting a user row neither
cascades nor errors — it silently orphans every child row. Erasure therefore
has to be written by hand, from one shared registry, or it drifts the moment
a new user-owned table is added (as it already had: NvoAttempt was missing
from guest_cleanup's copy of the list).
"""
import json

import pytest

from app.models.curriculum import ExerciseAttempt
from app.models.event_log import EventLog
from app.models.nvo_exam import NvoAttempt
from app.models.progress import (
    LessonProgress,
    UserBadge,
    UserDailyMission,
    UserProgress,
    UserXpProfile,
    XpEvent,
)
from app.models.saved_problem import SavedProblem
from app.models.user import User
from app.services.user_data import (
    USER_OWNED_TABLES,
    delete_user_account,
    export_user_data,
)


@pytest.fixture(autouse=True)
def _clean_user_owned_tables(db):
    """Wipe user-owned rows around every test in this module.

    Without this the suite trips over its own orphans: nothing cascades from
    `users`, and SQLite reassigns a deleted row's id to the next insert, so a
    later make_user() can land on an id that still has a UserXpProfile from
    an earlier test — which its UNIQUE(user_id) then rejects. That collision
    is the very bug this module exists to fix; here it is just noise.
    """
    yield
    for table in USER_OWNED_TABLES:
        db.query(table).delete(synchronize_session=False)
    db.query(EventLog).delete(synchronize_session=False)
    db.commit()


def _populate(db, user_id: int) -> None:
    """One row in every user-owned table, plus an event_logs entry."""
    db.add_all([
        UserProgress(user_id=user_id, topic_id=1, completed_exercises=1, total_exercises=2),
        LessonProgress(user_id=user_id, lesson_id=1, completed_exercises=1, total_exercises=2),
        UserXpProfile(user_id=user_id, total_xp=500, streak_days=3),
        XpEvent(user_id=user_id, source_type="test", xp_amount=50, reason="test"),
        UserBadge(user_id=user_id, badge_key="streak_7"),
        NvoAttempt(user_id=user_id, exam_id="abc123", percentage_correct=80),
        SavedProblem(
            user_id=user_id,
            source="exercise",
            source_ref="4271",
            snapshot_json='{"kind": "exercise", "question": "test"}',
        ),
        EventLog(
            log_type="bug_report",
            payload_json=json.dumps({"user_id": str(user_id), "message": "нещо не работи"}),
        ),
    ])
    db.commit()


# ─── The registry itself ─────────────────────────────────────────────────────

def test_every_user_owned_table_is_registered():
    """The registry is the single source of truth both erasure and the
    guest purge read. A table missing here is silently orphaned data."""
    registered = {table.__tablename__ for table in USER_OWNED_TABLES}

    assert registered == {
        "exercise_attempts",
        "user_progress",
        "lesson_progress",
        "user_xp_profiles",
        "xp_events",
        "user_badges",
        "user_daily_missions",
        "nvo_attempts",
        "saved_problems",
    }


# ─── Export (Art. 15 access / Art. 20 portability) ──────────────────────────

def test_export_includes_the_account_itself(db, make_user):
    user = make_user()

    data = export_user_data(db, user)

    assert data["account"]["id"] == user.id
    assert data["account"]["email"] == user.email


def test_export_includes_every_user_owned_table(db, make_user):
    user = make_user()
    _populate(db, user.id)

    data = export_user_data(db, user)

    assert data["progress"]["user_progress"]
    assert data["progress"]["lesson_progress"]
    assert data["progress"]["user_xp_profiles"][0]["total_xp"] == 500
    assert data["progress"]["xp_events"]
    assert data["progress"]["user_badges"][0]["badge_key"] == "streak_7"
    assert data["progress"]["nvo_attempts"][0]["exam_id"] == "abc123"


def test_export_includes_submitted_reports_and_feedback(db, make_user):
    user = make_user()
    _populate(db, user.id)

    data = export_user_data(db, user)

    assert any(item["message"] == "нещо не работи" for item in data["submitted_logs"])


def test_export_never_leaks_another_users_rows(db, make_user):
    mine = make_user()
    theirs = make_user()
    _populate(db, theirs.id)

    data = export_user_data(db, mine)

    assert data["progress"]["xp_events"] == []
    assert data["submitted_logs"] == []


def test_export_is_json_serialisable(db, make_user):
    """It is handed to the student as a download; datetimes must not blow up."""
    user = make_user()
    _populate(db, user.id)

    json.dumps(export_user_data(db, user), ensure_ascii=False)


# ─── Erasure (Art. 17) ───────────────────────────────────────────────────────

def test_delete_removes_the_user_row(db, make_user):
    user = make_user()
    user_id = user.id

    delete_user_account(db, user)

    assert db.query(User).filter(User.id == user_id).one_or_none() is None


def test_delete_removes_every_child_row(db, make_user):
    user = make_user()
    user_id = user.id
    _populate(db, user_id)

    delete_user_account(db, user)

    for table in USER_OWNED_TABLES:
        remaining = db.query(table).filter(table.user_id == user_id).count()
        assert remaining == 0, f"{table.__tablename__} still holds rows for a deleted user"


def test_delete_removes_their_submitted_logs(db, make_user):
    user = make_user()
    user_id = user.id
    _populate(db, user_id)

    delete_user_account(db, user)

    remaining = [
        row for row in db.query(EventLog).all()
        if json.loads(row.payload_json).get("user_id") in (str(user_id), user_id)
    ]
    assert remaining == []


def test_delete_reports_what_it_removed(db, make_user):
    user = make_user()
    _populate(db, user.id)

    counts = delete_user_account(db, user)

    assert counts["user_badges"] == 1
    assert counts["nvo_attempts"] == 1


def test_delete_never_touches_another_users_rows(db, make_user):
    mine = make_user()
    theirs = make_user()
    _populate(db, mine.id)
    _populate(db, theirs.id)

    delete_user_account(db, mine)

    assert db.query(XpEvent).filter(XpEvent.user_id == theirs.id).count() == 1
    assert db.query(User).filter(User.id == theirs.id).one_or_none() is not None
    surviving = [
        row for row in db.query(EventLog).all()
        if json.loads(row.payload_json).get("user_id") == str(theirs.id)
    ]
    assert len(surviving) == 1


def test_delete_removes_classes_the_user_taught_and_joined(db, make_user):
    """Classrooms key off teacher_id/student_id rather than a `user_id`
    column, so they sit outside USER_OWNED_TABLES and need erasing
    explicitly — otherwise a deleted teacher leaves a live join code and a
    roster of children behind."""
    from app.models.classroom import Classroom, ClassroomMember
    from app.services import classroom_service as svc

    teacher = make_user()
    student = make_user()
    taught = svc.create_classroom(db, teacher_id=teacher.id, name="Мой клас")
    svc.join_classroom(db, student_id=student.id, join_code=taught.join_code)

    other_teacher = make_user()
    joined = svc.create_classroom(db, teacher_id=other_teacher.id, name="Чужд клас")
    svc.join_classroom(db, student_id=teacher.id, join_code=joined.join_code)

    # Read the ids out before the delete: afterwards these instances are gone
    # from the database, and touching a lazy attribute would make SQLAlchemy
    # try to refresh a row that no longer exists.
    teacher_id, taught_id, joined_id = teacher.id, taught.id, joined.id

    counts = delete_user_account(db, teacher)
    db.expire_all()

    # The class they ran is gone, and so is its roster.
    assert db.query(Classroom).filter(Classroom.id == taught_id).one_or_none() is None
    assert db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == taught_id
    ).count() == 0
    # Their membership of someone else's class is gone, but that class isn't.
    assert db.query(ClassroomMember).filter(
        ClassroomMember.student_id == teacher_id
    ).count() == 0
    assert db.query(Classroom).filter(Classroom.id == joined_id).one_or_none() is not None
    assert counts["classrooms"] == 1

    db.query(ClassroomMember).delete(synchronize_session=False)
    db.query(Classroom).delete(synchronize_session=False)
    db.commit()


def test_export_includes_classes_taught_and_joined(db, make_user):
    from app.models.classroom import Classroom, ClassroomMember
    from app.services import classroom_service as svc

    teacher = make_user()
    student = make_user()
    taught = svc.create_classroom(db, teacher_id=teacher.id, name="Мой клас")
    svc.join_classroom(db, student_id=student.id, join_code=taught.join_code)

    data = export_user_data(db, student)

    assert [c["name"] for c in data["classrooms"]["joined"]] == ["Мой клас"]
    assert data["classrooms"]["taught"] == []

    db.query(ClassroomMember).delete(synchronize_session=False)
    db.query(Classroom).delete(synchronize_session=False)
    db.commit()


def test_delete_also_clears_mission_exercises(db, make_user):
    """user_mission_exercises has no user_id of its own — it hangs off
    user_daily_missions.mission_id, so it needs deleting by that link or it
    outlives the account."""
    from datetime import date as _date

    from app.models.progress import UserMissionExercise

    user = make_user()
    mission = UserDailyMission(
        user_id=user.id, mission_date=_date.today(),
        mission_key="k", title="t", description="d", lesson_id=1,
        required_difficulty="easy", target_count=3, route="/x",
    )
    db.add(mission)
    db.flush()
    db.add(UserMissionExercise(mission_id=mission.id, exercise_id=1, is_correct=True))
    db.commit()
    mission_id = mission.id

    counts = delete_user_account(db, user)

    assert counts["user_mission_exercises"] == 1
    assert db.query(UserMissionExercise).filter(
        UserMissionExercise.mission_id == mission_id
    ).count() == 0
