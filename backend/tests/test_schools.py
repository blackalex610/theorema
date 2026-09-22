"""The school: what a director logs into, and what they deliberately cannot see.

A director buys this for a building, not a class. They need to know whether
the cohort is ready for НВО, which classes are behind, and how many seats
they are paying for.

The consent design copies the one that already works for classes, one level
up: the director creates a school and gets a code, a teacher types the code
in, and a teacher attaches their own class. No one is enrolled by someone
else, at either level.

The sharpest decision here is negative and is pinned by tests: **a director
sees class-level aggregates, never another teacher's individual students.**
An 11-year-old consented to being visible to the teacher whose code they
typed. Nobody handed that child's record to the whole building, and an
easier privacy conversation with a school is worth more than the feature.
"""
import pytest
from fastapi import HTTPException

from app.models.classroom import Classroom, ClassroomMember
from app.models.nvo_exam import NvoAttempt, NvoAttemptItem
from app.models.school import School, SchoolMember
from app.services import classroom_service as classes
from app.services import school_service as svc


@pytest.fixture(autouse=True)
def _clean(db):
    def _clear():
        db.query(NvoAttemptItem).delete(synchronize_session=False)
        db.query(NvoAttempt).delete(synchronize_session=False)
        db.query(ClassroomMember).delete(synchronize_session=False)
        db.query(Classroom).delete(synchronize_session=False)
        db.query(SchoolMember).delete(synchronize_session=False)
        db.query(School).delete(synchronize_session=False)
        db.commit()

    _clear()
    yield
    _clear()


def _attempt(db, user_id: int, exam_id: str, *, items: list[tuple[str, bool]]) -> None:
    attempt = NvoAttempt(
        user_id=user_id,
        exam_id=exam_id,
        difficulty="actual",
        format="full",
        percentage_correct=round(100 * sum(1 for _, ok in items if ok) / len(items)),
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


# ─── Creating and joining ────────────────────────────────────────────────────

def test_creating_a_school_issues_a_teacher_join_code(db, make_user):
    director = make_user()

    school = svc.create_school(db, director_id=director.id, name="СУ Иван Вазов", city="Пловдив")

    assert school.name == "СУ Иван Вазов"
    assert school.director_id == director.id
    assert len(school.join_code) == svc.CODE_LENGTH


def test_join_codes_avoid_characters_that_get_misread(db, make_user):
    """Same reasoning as class codes: this gets read off a screen and typed."""
    director = make_user()

    codes = {
        svc.create_school(db, director_id=make_user().id, name=f"Училище {i}").join_code
        for i in range(12)
    }

    assert all(not (set(code) & set("O0I1L")) for code in codes)


def test_a_teacher_joins_a_school_with_its_code(db, make_user):
    director = make_user()
    teacher = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ Иван Вазов")

    joined = svc.join_school(db, teacher_id=teacher.id, join_code=school.join_code)

    assert joined.id == school.id
    assert [s.id for s in svc.list_schools_for_teacher(db, teacher_id=teacher.id)] == [school.id]


def test_an_unknown_code_is_rejected(db, make_user):
    teacher = make_user()

    with pytest.raises(HTTPException) as exc:
        svc.join_school(db, teacher_id=teacher.id, join_code="ZZZZZZ")

    assert exc.value.status_code == 404


# ─── Attaching a class is the teacher's choice ───────────────────────────────

def test_a_teacher_attaches_their_own_class_to_the_school(db, make_user):
    director = make_user()
    teacher = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ")
    svc.join_school(db, teacher_id=teacher.id, join_code=school.join_code)
    classroom = classes.create_classroom(db, teacher_id=teacher.id, name="7А", grade_level=7)

    svc.attach_classroom(
        db, school_id=school.id, classroom_id=classroom.id, teacher_id=teacher.id
    )

    db.refresh(classroom)
    assert classroom.school_id == school.id


def test_a_director_cannot_attach_someone_elses_class(db, make_user):
    """The teacher opts their class in, exactly as the student opts into the
    class. Consent runs the same direction at both levels."""
    director = make_user()
    teacher = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ")
    svc.join_school(db, teacher_id=teacher.id, join_code=school.join_code)
    classroom = classes.create_classroom(db, teacher_id=teacher.id, name="7А")

    with pytest.raises(HTTPException) as exc:
        svc.attach_classroom(
            db, school_id=school.id, classroom_id=classroom.id, teacher_id=director.id
        )

    assert exc.value.status_code == 404


def test_a_teacher_who_has_not_joined_cannot_attach_a_class(db, make_user):
    director = make_user()
    outsider = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ")
    classroom = classes.create_classroom(db, teacher_id=outsider.id, name="7А")

    with pytest.raises(HTTPException) as exc:
        svc.attach_classroom(
            db, school_id=school.id, classroom_id=classroom.id, teacher_id=outsider.id
        )

    assert exc.value.status_code == 403


def test_a_teacher_can_detach_their_class_again(db, make_user):
    director = make_user()
    teacher = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ")
    svc.join_school(db, teacher_id=teacher.id, join_code=school.join_code)
    classroom = classes.create_classroom(db, teacher_id=teacher.id, name="7А")
    svc.attach_classroom(
        db, school_id=school.id, classroom_id=classroom.id, teacher_id=teacher.id
    )

    svc.detach_classroom(db, classroom_id=classroom.id, teacher_id=teacher.id)

    db.refresh(classroom)
    assert classroom.school_id is None


# ─── The director's dashboard ────────────────────────────────────────────────

def _school_with_class(db, make_user, *, students: int, grade: int = 7):
    director = make_user()
    teacher = make_user()
    school = svc.create_school(db, director_id=director.id, name="СУ Иван Вазов")
    svc.join_school(db, teacher_id=teacher.id, join_code=school.join_code)
    classroom = classes.create_classroom(
        db, teacher_id=teacher.id, name="7А", grade_level=grade
    )
    svc.attach_classroom(
        db, school_id=school.id, classroom_id=classroom.id, teacher_id=teacher.id
    )
    members = [make_user() for _ in range(students)]
    for student in members:
        classes.join_classroom(db, student_id=student.id, join_code=classroom.join_code)
    return director, teacher, school, classroom, members


def test_overview_counts_seats_across_attached_classes(db, make_user):
    director, _teacher, school, _classroom, _students = _school_with_class(
        db, make_user, students=3
    )

    overview = svc.build_school_overview(db, school_id=school.id, director_id=director.id)

    assert overview["class_count"] == 1
    assert overview["teacher_count"] == 1
    assert overview["seats_used"] == 3


def test_a_class_not_attached_is_not_in_the_overview(db, make_user):
    director, teacher, school, _classroom, _students = _school_with_class(
        db, make_user, students=2
    )
    unattached = classes.create_classroom(db, teacher_id=teacher.id, name="6Б")
    classes.join_classroom(db, student_id=make_user().id, join_code=unattached.join_code)

    overview = svc.build_school_overview(db, school_id=school.id, director_id=director.id)

    assert overview["class_count"] == 1
    assert overview["seats_used"] == 2


def test_only_the_director_reads_the_overview(db, make_user):
    _director, teacher, school, _classroom, _students = _school_with_class(
        db, make_user, students=1
    )

    with pytest.raises(HTTPException) as exc:
        svc.build_school_overview(db, school_id=school.id, director_id=teacher.id)

    assert exc.value.status_code == 404


def test_readiness_buckets_the_latest_score_per_student(db, make_user):
    director, _teacher, school, _classroom, students = _school_with_class(
        db, make_user, students=2
    )
    _attempt(db, students[0].id, "s1", items=[("inequality", True)] * 10)   # 100%
    _attempt(db, students[1].id, "s2", items=[("inequality", False)] * 10)  # 0%

    overview = svc.build_school_overview(db, school_id=school.id, director_id=director.id)

    buckets = {b["key"]: b["students"] for b in overview["readiness"]}
    assert buckets["excellent"] == 1
    assert buckets["at_risk"] == 1


def test_school_diagnostics_aggregate_across_classes(db, make_user):
    director, _teacher, school, _classroom, students = _school_with_class(
        db, make_user, students=2
    )
    _attempt(db, students[0].id, "s1", items=[("inequality", False)] * 3)
    _attempt(db, students[1].id, "s2", items=[("inequality", True)] * 3)

    overview = svc.build_school_overview(db, school_id=school.id, director_id=director.id)

    inequality = next(t for t in overview["topics"] if t["key"] == "inequality")
    assert inequality["asked"] == 6
    assert inequality["percent_correct"] == 50


# ─── What a director must NOT see ────────────────────────────────────────────

def test_the_overview_never_names_an_individual_student(db, make_user):
    """A child consented to being visible to the teacher whose code they
    typed — not to the whole building. The director gets cohort numbers."""
    director, _teacher, school, _classroom, students = _school_with_class(
        db, make_user, students=2
    )
    _attempt(db, students[0].id, "s1", items=[("inequality", True)] * 3)

    overview = svc.build_school_overview(db, school_id=school.id, director_id=director.id)

    rendered = repr(overview)
    for student in students:
        assert str(student.email) not in rendered
        assert f'"student_id": {student.id}' not in rendered
    assert "roster" not in overview
    for row in overview["classes"]:
        assert "roster" not in row
        assert "students" not in row or isinstance(row.get("students"), int)


def test_a_director_cannot_read_a_class_roster_through_the_school(db, make_user):
    """Owning the school is not owning the class. The roster check is
    unchanged: you read the classes you teach."""
    director, _teacher, _school, classroom, _students = _school_with_class(
        db, make_user, students=1
    )

    with pytest.raises(HTTPException) as exc:
        classes.build_roster(db, classroom_id=classroom.id, teacher_id=director.id)

    assert exc.value.status_code == 404
