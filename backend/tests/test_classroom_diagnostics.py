"""What a teacher actually opens: which topics is this class failing.

The roster answers "how is Мария doing" with four aggregate numbers. It
cannot answer "what should I reteach on Monday", which is the question a
teacher has. These aggregations answer it off nvo_attempt_items.

The tests here are mostly about *not misleading* a teacher: a topic asked
once is not evidence, a topic the taxonomy could not identify is not a
teaching instruction, and a class's numbers must never include a student
who is not in it.
"""
import pytest
from fastapi import HTTPException

from app.models.classroom import Classroom, ClassroomMember
from app.models.nvo_exam import NvoAttempt, NvoAttemptItem
from app.models.progress import UserXpProfile
from app.services import classroom_analytics as analytics
from app.services import classroom_service as svc


@pytest.fixture(autouse=True)
def _clean(db):
    def _clear():
        db.query(NvoAttemptItem).delete(synchronize_session=False)
        db.query(NvoAttempt).delete(synchronize_session=False)
        db.query(ClassroomMember).delete(synchronize_session=False)
        db.query(Classroom).delete(synchronize_session=False)
        db.query(UserXpProfile).delete(synchronize_session=False)
        db.commit()

    _clear()
    yield
    _clear()


def _attempt(db, user_id: int, exam_id: str, *, items: list[tuple[str, bool]]) -> NvoAttempt:
    """One graded sitting: (topic_key, is_correct) per question."""
    attempt = NvoAttempt(
        user_id=user_id,
        exam_id=exam_id,
        difficulty="actual",
        format="full",
        percentage_correct=round(
            100 * sum(1 for _, ok in items if ok) / len(items)
        ) if items else 0,
    )
    db.add(attempt)
    db.flush()
    for number, (topic_key, ok) in enumerate(items, start=1):
        db.add(
            NvoAttemptItem(
                attempt_id=attempt.id,
                user_id=user_id,
                question_number=number,
                topic_key=topic_key,
                kind="mc",
                is_correct=ok,
                points_awarded=1 if ok else 0,
                points_max=1,
            )
        )
    db.commit()
    return attempt


def _class_with_students(db, make_user, count: int):
    teacher = make_user()
    classroom = svc.create_classroom(db, teacher_id=teacher.id, name="7А", grade_level=7)
    students = [make_user() for _ in range(count)]
    for student in students:
        svc.join_classroom(db, student_id=student.id, join_code=classroom.join_code)
    return teacher, classroom, students


# ─── Ownership ───────────────────────────────────────────────────────────────

def test_another_teacher_cannot_read_a_class_diagnostic(db, make_user):
    _teacher, classroom, _students = _class_with_students(db, make_user, 1)
    stranger = make_user()

    with pytest.raises(HTTPException) as exc:
        analytics.build_class_diagnostics(
            db, classroom_id=classroom.id, teacher_id=stranger.id
        )

    assert exc.value.status_code == 404


# ─── Aggregation ─────────────────────────────────────────────────────────────

def test_topic_percentages_come_from_the_whole_class(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 2)
    _attempt(db, students[0].id, "e1", items=[("inequality", False)] * 3)
    _attempt(db, students[1].id, "e2", items=[("inequality", True)] * 3)

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    inequality = next(t for t in result["topics"] if t["key"] == "inequality")
    assert inequality["asked"] == 6
    assert inequality["correct"] == 3
    assert inequality["percent_correct"] == 50
    assert inequality["students"] == 2


def test_a_student_outside_the_class_is_not_counted(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    outsider = make_user()
    _attempt(db, students[0].id, "e1", items=[("inequality", True)] * 2)
    _attempt(db, outsider.id, "e2", items=[("inequality", False)] * 10)

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    inequality = next(t for t in result["topics"] if t["key"] == "inequality")
    assert inequality["asked"] == 2
    assert inequality["percent_correct"] == 100


def test_topics_roll_up_into_curriculum_strands(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _attempt(
        db,
        students[0].id,
        "e1",
        items=[("inequality", True), ("linear_equation", False), ("geom_triangle", False)],
    )

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    algebra = next(s for s in result["strands"] if s["key"] == "algebra")
    assert algebra["asked"] == 2
    assert algebra["correct"] == 1
    assert algebra["percent_correct"] == 50


def test_a_class_with_no_attempts_reports_no_topics_rather_than_failing(db, make_user):
    teacher, classroom, _students = _class_with_students(db, make_user, 2)

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    assert result["topics"] == []
    assert result["weakest"] == []
    assert result["students_with_data"] == 0


# ─── Not misleading the teacher ──────────────────────────────────────────────

def test_weakest_topics_ignore_ones_asked_too_few_times(db, make_user):
    """One wrong answer on one question is not a class weakness. Ranking it
    first would send a teacher to reteach a topic on a sample of one."""
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _attempt(
        db,
        students[0].id,
        "e1",
        items=[("geom_triangle", False)] + [("inequality", False)] * 4 + [("inequality", True)],
    )

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    weakest_keys = [t["key"] for t in result["weakest"]]
    assert "inequality" in weakest_keys
    assert "geom_triangle" not in weakest_keys, "ranked a topic asked once as a class weakness"


def test_unidentified_topics_are_never_offered_as_a_weakness(db, make_user):
    """`other` is a bucket of questions the taxonomy did not recognise — a
    data-quality signal for us, not something to reteach."""
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _attempt(db, students[0].id, "e1", items=[("other", False)] * 8)

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    assert "other" not in [t["key"] for t in result["weakest"]]


def test_weakest_are_ordered_worst_first(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _attempt(
        db,
        students[0].id,
        "e1",
        items=(
            [("inequality", False)] * 3
            + [("linear_equation", False)] * 2 + [("linear_equation", True)] * 2
            + [("powers", True)] * 3
        ),
    )

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    assert [t["key"] for t in result["weakest"]][:2] == ["inequality", "linear_equation"]


def test_topics_carry_the_bulgarian_label_the_teacher_reads(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _attempt(db, students[0].id, "e1", items=[("inequality", True)] * 3)

    result = analytics.build_class_diagnostics(
        db, classroom_id=classroom.id, teacher_id=teacher.id
    )

    inequality = next(t for t in result["topics"] if t["key"] == "inequality")
    assert inequality["label"] == "Неравенства"
    assert inequality["strand_label"] == "Алгебра"


# ─── One student, drilled into ───────────────────────────────────────────────

def test_student_profile_is_scoped_to_that_student(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 2)
    _attempt(db, students[0].id, "e1", items=[("inequality", True)] * 2)
    _attempt(db, students[1].id, "e2", items=[("inequality", False)] * 2)

    profile = analytics.build_student_profile(
        db, classroom_id=classroom.id, teacher_id=teacher.id, student_id=students[0].id
    )

    inequality = next(t for t in profile["topics"] if t["key"] == "inequality")
    assert inequality["percent_correct"] == 100
    assert profile["attempts"][0]["exam_id"] == "e1"
    # The client greys out small samples with the server's own threshold
    # rather than a second copy of the constant that could drift.
    assert profile["min_asked_for_ranking"] == analytics.MIN_ASKED_FOR_RANKING


def test_a_student_who_is_not_in_the_class_is_not_readable(db, make_user):
    """Otherwise any teacher could read any child's profile by guessing ids."""
    teacher, classroom, _students = _class_with_students(db, make_user, 1)
    outsider = make_user()

    with pytest.raises(HTTPException) as exc:
        analytics.build_student_profile(
            db, classroom_id=classroom.id, teacher_id=teacher.id, student_id=outsider.id
        )

    assert exc.value.status_code == 404
