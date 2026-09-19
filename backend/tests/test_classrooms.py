"""Classrooms: the foundation under both the teacher and the parent product.

Until now there was no teacher product at all — no class, no roster, no way
for any adult to see a student's work. Every occurrence of "учител" in the
codebase was an LLM system prompt or a testimonial.

Two deliberate design decisions are pinned here:

* **Teacher-ness is not a role flag.** You are the teacher of the classes you
  created and a student of the classes you joined. One less piece of mutable
  account state to get wrong, and it matches how a person actually uses this.
* **The join code is the consent.** A teacher cannot pull a student into a
  class; the student types the code in. That is what makes an adult seeing a
  child's progress lawful, so it is a test, not a convention.
"""
import pytest
from fastapi import HTTPException

from app.models.classroom import Classroom, ClassroomMember
from app.models.nvo_exam import NvoAttempt
from app.models.progress import UserXpProfile
from app.services import classroom_service as svc


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(ClassroomMember).delete(synchronize_session=False)
    db.query(Classroom).delete(synchronize_session=False)
    db.query(NvoAttempt).delete(synchronize_session=False)
    db.query(UserXpProfile).delete(synchronize_session=False)
    db.commit()


# ─── Creating a class ────────────────────────────────────────────────────────

def test_creating_a_class_issues_a_join_code(db, make_user):
    teacher = make_user()

    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А математика")

    assert classroom.name == "7А математика"
    assert classroom.teacher_id == teacher.id
    assert classroom.join_code


def test_join_codes_are_unique_across_classes(db, make_user):
    teacher = make_user()

    codes = {
        svc.create_classroom(db, teacher_id=teacher.id, name=f"Клас {i}").join_code
        for i in range(25)
    }

    assert len(codes) == 25


def test_join_codes_avoid_characters_that_get_misread(db, make_user):
    """A code is read off a whiteboard by a 12-year-old: no O/0, no I/1/L."""
    teacher = make_user()

    for i in range(25):
        code = svc.create_classroom(db, teacher_id=teacher.id, name=f"К{i}").join_code
        assert not set(code) & set("O0I1L"), code
        assert code == code.upper()


def test_a_teacher_sees_only_their_own_classes(db, make_user):
    mine, theirs = make_user(), make_user()
    svc.create_classroom(db, teacher_id=mine.id, name="Мой клас")
    svc.create_classroom(db, teacher_id=theirs.id, name="Чужд клас")

    names = [c.name for c in svc.list_classrooms_for_teacher(db, mine.id)]

    assert names == ["Мой клас"]


# ─── Joining ─────────────────────────────────────────────────────────────────

def test_a_student_joins_with_the_code(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")

    joined = svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    assert joined.id == classroom.id
    assert [m.student_id for m in svc.list_members(db, classroom.id)] == [student.id]


def test_the_code_is_accepted_case_insensitively(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")

    joined = svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code.lower())

    assert joined.id == classroom.id


def test_joining_twice_does_not_duplicate_the_student(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")

    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    assert len(svc.list_members(db, classroom.id)) == 1


def test_an_unknown_code_is_rejected(db, make_user):
    student = make_user()

    with pytest.raises(HTTPException) as exc:
        svc.join_classroom(db, student_id=student.id, join_code="ZZZZZZ")
    assert exc.value.status_code == 404


def test_a_teacher_cannot_join_their_own_class_as_a_student(db, make_user):
    teacher = make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")

    with pytest.raises(HTTPException) as exc:
        svc.join_classroom(db, student_id=teacher.id, join_code=classroom.join_code)
    assert exc.value.status_code == 400


def test_joining_an_archived_class_is_rejected(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.archive_classroom(db, classroom_id=classroom.id, teacher_id=teacher.id)

    with pytest.raises(HTTPException) as exc:
        svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)
    assert exc.value.status_code == 410


# ─── The roster a teacher actually looks at ─────────────────────────────────

def test_the_roster_reports_real_progress_not_placeholders(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    db.add(UserXpProfile(user_id=student.id, total_xp=1200, streak_days=4))
    db.add_all([
        NvoAttempt(user_id=student.id, exam_id="e1", percentage_correct=60,
                   mcq_score=12, mcq_max_score=20, open_score=0, open_max_score=3),
        NvoAttempt(user_id=student.id, exam_id="e2", percentage_correct=80,
                   mcq_score=16, mcq_max_score=20, open_score=2, open_max_score=3),
    ])
    db.commit()

    rows = svc.build_roster(db, classroom_id=classroom.id, teacher_id=teacher.id)

    assert len(rows) == 1
    row = rows[0]
    assert row["student_id"] == student.id
    assert row["total_xp"] == 1200
    assert row["exams_taken"] == 2
    assert row["average_exam_score"] == 70  # (60 + 80) / 2
    assert row["best_exam_score"] == 80
    assert row["level"] >= 1


def test_a_student_with_no_activity_still_appears_on_the_roster(db, make_user):
    """A teacher needs to see who has done nothing — that is the point."""
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    rows = svc.build_roster(db, classroom_id=classroom.id, teacher_id=teacher.id)

    assert len(rows) == 1
    assert rows[0]["exams_taken"] == 0
    assert rows[0]["total_xp"] == 0
    assert rows[0]["average_exam_score"] is None


def test_another_teacher_cannot_read_the_roster(db, make_user):
    teacher, intruder, student = make_user(), make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    with pytest.raises(HTTPException) as exc:
        svc.build_roster(db, classroom_id=classroom.id, teacher_id=intruder.id)
    assert exc.value.status_code == 404


# ─── Leaving and removing ────────────────────────────────────────────────────

def test_a_teacher_can_remove_a_student(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    svc.remove_member(db, classroom_id=classroom.id, teacher_id=teacher.id, student_id=student.id)

    assert svc.list_members(db, classroom.id) == []


def test_a_student_can_leave_on_their_own(db, make_user):
    """Withdrawing consent has to be as easy as giving it."""
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    svc.leave_classroom(db, classroom_id=classroom.id, student_id=student.id)

    assert svc.list_members(db, classroom.id) == []


def test_a_student_sees_the_classes_they_joined(db, make_user):
    teacher, student = make_user(), make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)

    assert [c.id for c in svc.list_classrooms_for_student(db, student.id)] == [classroom.id]
