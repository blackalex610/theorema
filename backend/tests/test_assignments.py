"""Assigning one paper to a class — "can I assign this?", answered.

The class sits *the same generated paper*, which is what makes "17 of 26
missed question 7" a sentence anyone can say. Two mechanics carry the whole
feature and both are easy to get quietly wrong:

* **The paper has to outlive the 24h exam TTL.** Generated exams are cache
  rows that get purged; an assignment due next Tuesday whose paper vanished
  on Saturday is worse than no assignment.
* **Sitting an assigned exam must not spend the student's one exam a day.**
  The teacher already paid for the generation. A student locked out of their
  own homework by the free-tier quota would be the product's worst moment.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.classroom import Classroom, ClassroomAssignment, ClassroomMember
from app.models.nvo_exam import GeneratedExam, NvoAttempt, NvoAttemptItem
from app.services import assignment_service as svc
from app.services import classroom_service as classes
from app.services import nvo_exam_store


@pytest.fixture(autouse=True)
def _clean(db):
    def _clear():
        db.query(NvoAttemptItem).delete(synchronize_session=False)
        db.query(NvoAttempt).delete(synchronize_session=False)
        db.query(ClassroomAssignment).delete(synchronize_session=False)
        db.query(ClassroomMember).delete(synchronize_session=False)
        db.query(Classroom).delete(synchronize_session=False)
        db.query(GeneratedExam).delete(synchronize_session=False)
        db.commit()
        nvo_exam_store.clear_cache()

    _clear()
    yield
    _clear()


def _stored_exam(exam_id: str) -> None:
    nvo_exam_store.save_exam(
        exam_id,
        {
            "exam_id": exam_id,
            "questions": [
                {
                    "number": 1,
                    "question": "MCQ 1",
                    "topic": "inequality_integer_bound",
                    "difficulty": "easy",
                    "diagram": False,
                    "options": ["А) x", "Б) y", "В) z", "Г) w"],
                    "correct_answer": "А",
                    "kind": "mc",
                }
            ],
            "difficulty": "actual",
            "format": "full",
        },
    )


def _class_with_students(db, make_user, count: int):
    teacher = make_user()
    classroom = classes.create_classroom(db, teacher_id=teacher.id, name="7А", grade_level=7)
    students = [make_user() for _ in range(count)]
    for student in students:
        classes.join_classroom(db, student_id=student.id, join_code=classroom.join_code)
    return teacher, classroom, students


def _attempt(db, user_id: int, exam_id: str, *, results: list[bool]) -> NvoAttempt:
    attempt = NvoAttempt(
        user_id=user_id,
        exam_id=exam_id,
        difficulty="actual",
        format="full",
        percentage_correct=round(100 * sum(results) / len(results)),
    )
    db.add(attempt)
    db.flush()
    for number, ok in enumerate(results, start=1):
        db.add(
            NvoAttemptItem(
                attempt_id=attempt.id,
                user_id=user_id,
                question_number=number,
                topic_key="inequality",
                kind="mc",
                is_correct=ok,
                points_awarded=1 if ok else 0,
                points_max=1,
            )
        )
    db.commit()
    return attempt


# ─── Creating ────────────────────────────────────────────────────────────────

def test_creating_an_assignment_pins_the_paper_past_the_exam_ttl(db, make_user):
    """The default TTL is 24h. A paper due in a week must survive until then."""
    teacher, classroom, _ = _class_with_students(db, make_user, 1)
    _stored_exam("pinned01")
    due = datetime.utcnow() + timedelta(days=7)

    svc.create_assignment(
        db,
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        title="Контролно 1",
        exam_id="pinned01",
        due_at=due,
    )

    row = db.query(GeneratedExam).filter(GeneratedExam.exam_id == "pinned01").one()
    assert row.expires_at > due, "the assigned paper expires before it is due"


def test_an_assignment_without_a_due_date_still_outlives_the_default_ttl(db, make_user):
    teacher, classroom, _ = _class_with_students(db, make_user, 1)
    _stored_exam("pinned02")
    default_ttl_end = datetime.utcnow() + nvo_exam_store.EXAM_TTL

    svc.create_assignment(
        db,
        classroom_id=classroom.id,
        teacher_id=teacher.id,
        title="Без срок",
        exam_id="pinned02",
        due_at=None,
    )

    row = db.query(GeneratedExam).filter(GeneratedExam.exam_id == "pinned02").one()
    assert row.expires_at > default_ttl_end


def test_only_the_owning_teacher_can_assign_to_a_class(db, make_user):
    _teacher, classroom, _ = _class_with_students(db, make_user, 1)
    stranger = make_user()
    _stored_exam("pinned03")

    with pytest.raises(HTTPException) as exc:
        svc.create_assignment(
            db,
            classroom_id=classroom.id,
            teacher_id=stranger.id,
            title="Чуждо",
            exam_id="pinned03",
            due_at=None,
        )

    assert exc.value.status_code == 404


# ─── The student's side ──────────────────────────────────────────────────────

def test_a_student_in_the_class_sees_the_assignment(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _stored_exam("paper01")
    svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно 1", exam_id="paper01", due_at=None,
    )

    mine = svc.list_assignments_for_student(db, student_id=students[0].id)

    assert [a["title"] for a in mine] == ["Контролно 1"]
    assert mine[0]["class_name"] == "7А"


def test_a_student_outside_the_class_sees_nothing(db, make_user):
    teacher, classroom, _ = _class_with_students(db, make_user, 1)
    outsider = make_user()
    _stored_exam("paper02")
    svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper02", due_at=None,
    )

    assert svc.list_assignments_for_student(db, student_id=outsider.id) == []


def test_opening_an_assignment_gives_every_student_the_same_paper(db, make_user):
    """Comparable results per question is the entire point of assigning."""
    teacher, classroom, students = _class_with_students(db, make_user, 2)
    _stored_exam("paper03")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper03", due_at=None,
    )

    first = svc.exam_id_for_student(db, assignment_id=assignment.id, student_id=students[0].id)
    second = svc.exam_id_for_student(db, assignment_id=assignment.id, student_id=students[1].id)

    assert first == second == "paper03"


def test_a_non_member_cannot_open_the_assigned_paper(db, make_user):
    teacher, classroom, _ = _class_with_students(db, make_user, 1)
    outsider = make_user()
    _stored_exam("paper04")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper04", due_at=None,
    )

    with pytest.raises(HTTPException) as exc:
        svc.exam_id_for_student(db, assignment_id=assignment.id, student_id=outsider.id)

    assert exc.value.status_code == 404


def test_a_closed_assignment_cannot_be_opened(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _stored_exam("paper05")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper05", due_at=None,
    )
    svc.close_assignment(db, assignment_id=assignment.id, teacher_id=teacher.id)

    with pytest.raises(HTTPException) as exc:
        svc.exam_id_for_student(db, assignment_id=assignment.id, student_id=students[0].id)

    assert exc.value.status_code == 410


# ─── What the teacher gets back ──────────────────────────────────────────────

def test_completion_is_derived_from_graded_attempts(db, make_user):
    """No submissions table: NvoAttempt already has UNIQUE(user_id, exam_id),
    so "did this student sit it" is a query, not a second source of truth."""
    teacher, classroom, students = _class_with_students(db, make_user, 3)
    _stored_exam("paper06")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper06", due_at=None,
    )
    _attempt(db, students[0].id, "paper06", results=[True, True])
    _attempt(db, students[1].id, "paper06", results=[False, True])

    report = svc.build_assignment_report(
        db, assignment_id=assignment.id, teacher_id=teacher.id
    )

    assert report["submitted_count"] == 2
    assert report["student_count"] == 3
    by_id = {r["student_id"]: r for r in report["rows"]}
    assert by_id[students[0].id]["percentage_correct"] == 100
    assert by_id[students[2].id]["submitted"] is False


def test_report_says_how_many_students_missed_each_question(db, make_user):
    """Only meaningful because the class sat one paper."""
    teacher, classroom, students = _class_with_students(db, make_user, 2)
    _stored_exam("paper07")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper07", due_at=None,
    )
    _attempt(db, students[0].id, "paper07", results=[True, False])
    _attempt(db, students[1].id, "paper07", results=[False, False])

    report = svc.build_assignment_report(
        db, assignment_id=assignment.id, teacher_id=teacher.id
    )

    by_number = {q["question_number"]: q for q in report["questions"]}
    assert by_number[1]["wrong"] == 1
    assert by_number[2]["wrong"] == 2
    assert by_number[2]["answered"] == 2


def test_an_attempt_at_another_paper_is_not_counted_as_submitted(db, make_user):
    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _stored_exam("paper08")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper08", due_at=None,
    )
    _attempt(db, students[0].id, "some-other-exam", results=[True])

    report = svc.build_assignment_report(
        db, assignment_id=assignment.id, teacher_id=teacher.id
    )

    assert report["submitted_count"] == 0


def test_opening_homework_does_not_spend_the_students_daily_exam(db, make_user):
    """The free tier allows one exam a day. If homework consumed it, a
    student could be locked out of their own assignment by having practised
    that morning — and the teacher already paid a credit to generate it."""
    import asyncio

    from app.routers.assignments import open_assignment

    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _stored_exam("credit01")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Домашно", exam_id="credit01", due_at=None,
    )
    student = students[0]
    before = student.nvo_exams_today

    exam = asyncio.run(
        open_assignment(assignment_id=assignment.id, current_user=student, db=db)
    )

    db.refresh(student)
    assert student.nvo_exams_today == before, "homework charged the student a daily exam credit"
    assert exam.exam_id == "credit01"


def test_the_paper_handed_to_a_student_carries_no_answer_key(db, make_user):
    import asyncio

    from app.routers.assignments import open_assignment

    teacher, classroom, students = _class_with_students(db, make_user, 1)
    _stored_exam("credit02")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Домашно", exam_id="credit02", due_at=None,
    )

    exam = asyncio.run(
        open_assignment(assignment_id=assignment.id, current_user=students[0], db=db)
    )

    assert all(q.correct_answer is None for q in exam.questions)


def test_another_teacher_cannot_read_the_report(db, make_user):
    teacher, classroom, _ = _class_with_students(db, make_user, 1)
    stranger = make_user()
    _stored_exam("paper09")
    assignment = svc.create_assignment(
        db, classroom_id=classroom.id, teacher_id=teacher.id,
        title="Контролно", exam_id="paper09", due_at=None,
    )

    with pytest.raises(HTTPException) as exc:
        svc.build_assignment_report(
            db, assignment_id=assignment.id, teacher_id=stranger.id
        )

    assert exc.value.status_code == 404
