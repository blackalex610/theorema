"""The teacher and school flows end to end, through real HTTP routing.

The service tests prove the rules; these prove the routes are wired to them
— that a path exists, sits behind a session, and hands back what the
frontend reads. (An earlier slip in this work left /nvo/submit's decorator
on the wrong function; only a routing-level test notices that kind of
mistake.)
"""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.classroom import Classroom, ClassroomAssignment, ClassroomMember
from app.models.nvo_exam import GeneratedExam, NvoAttempt, NvoAttemptItem
from app.models.school import School, SchoolMember

client = TestClient(app)

_ip_counter = itertools.count(100)


def _session() -> tuple[int, dict]:
    res = client.post(
        "/auth/guest",
        headers={"X-Forwarded-For": f"198.51.100.{next(_ip_counter) % 254 + 1}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture(autouse=True)
def _clean(db):
    def _clear():
        db.query(NvoAttemptItem).delete(synchronize_session=False)
        db.query(NvoAttempt).delete(synchronize_session=False)
        db.query(ClassroomAssignment).delete(synchronize_session=False)
        db.query(ClassroomMember).delete(synchronize_session=False)
        db.query(Classroom).delete(synchronize_session=False)
        db.query(SchoolMember).delete(synchronize_session=False)
        db.query(School).delete(synchronize_session=False)
        db.query(GeneratedExam).delete(synchronize_session=False)
        db.commit()

    _clear()
    yield
    _clear()


@pytest.mark.parametrize("method,path", [
    ("get", "/classrooms/1/diagnostics"),
    ("get", "/classrooms/1/students/2"),
    ("post", "/assignments"),
    ("get", "/assignments/mine"),
    ("get", "/assignments/class/1"),
    ("get", "/assignments/1"),
    ("post", "/assignments/1/open"),
    ("post", "/schools"),
    ("get", "/schools"),
    ("get", "/schools/mine"),
    ("post", "/schools/join"),
    ("get", "/schools/1"),
])
def test_every_new_route_requires_a_session(method, path):
    kwargs = {"json": {}} if method == "post" else {}
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 401, f"{method.upper()} {path} was reachable anonymously"


def test_a_teacher_attaches_a_class_and_the_director_sees_it():
    _, director = _session()
    _, teacher = _session()

    school = client.post("/schools", json={"name": "СУ Иван Вазов", "city": "Пловдив"}, headers=director).json()
    assert client.post("/schools/join", json={"join_code": school["join_code"]}, headers=teacher).status_code == 200
    classroom = client.post("/classrooms", json={"name": "7А", "grade_level": 7}, headers=teacher).json()

    res = client.post(
        f"/schools/{school['id']}/classrooms",
        json={"classroom_id": classroom["id"]},
        headers=teacher,
    )
    assert res.status_code == 200, res.text

    # The class payload tells its teacher which school it sits in.
    detail = client.get(f"/classrooms/{classroom['id']}", headers=teacher).json()
    assert detail["school_id"] == school["id"]

    overview = client.get(f"/schools/{school['id']}", headers=director)
    assert overview.status_code == 200, overview.text
    assert overview.json()["class_count"] == 1


def test_a_director_cannot_open_a_school_they_did_not_create():
    _, director = _session()
    _, stranger = _session()
    school = client.post("/schools", json={"name": "СУ"}, headers=director).json()

    assert client.get(f"/schools/{school['id']}", headers=stranger).status_code == 404


def test_homework_opens_even_after_the_student_spent_their_daily_exam():
    """The free tier's one exam a day must never stand between a student and
    their homework — the teacher already paid for the paper."""
    _, teacher = _session()
    _, student = _session()

    classroom = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": classroom["join_code"]}, headers=student)

    created = client.post(
        "/assignments",
        json={"classroom_id": classroom["id"], "title": "Контролно 1"},
        headers=teacher,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    # Spend the student's own daily exam on ordinary practice first.
    practice = client.post("/nvo/generate", json={}, headers=student)
    assert practice.status_code == 200, practice.text
    assert client.post("/nvo/generate", json={}, headers=student).status_code != 200, (
        "precondition: the student's daily exam should now be spent"
    )

    mine = client.get("/assignments/mine", headers=student).json()["assignments"]
    assert [a["id"] for a in mine] == [assignment_id]

    opened = client.post(f"/assignments/{assignment_id}/open", headers=student)
    assert opened.status_code == 200, opened.text
    paper = opened.json()
    assert paper["questions"], "the assigned paper came back empty"
    assert all(q.get("correct_answer") is None for q in paper["questions"])


def test_the_teacher_report_lists_who_has_not_handed_in():
    _, teacher = _session()
    student_id, student = _session()

    classroom = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": classroom["join_code"]}, headers=student)
    assignment = client.post(
        "/assignments",
        json={"classroom_id": classroom["id"], "title": "Контролно"},
        headers=teacher,
    ).json()

    report = client.get(f"/assignments/{assignment['id']}", headers=teacher)

    assert report.status_code == 200, report.text
    body = report.json()
    assert body["submitted_count"] == 0
    assert [(r["student_id"], r["submitted"]) for r in body["rows"]] == [(student_id, False)]


def test_a_due_date_sent_by_a_browser_is_accepted():
    """Browsers send `toISOString()` — UTC with a trailing Z, which pydantic
    parses as timezone-aware. Every stored datetime in this schema is naive
    UTC, and comparing the two raises TypeError, so the route has to
    normalise before anything is compared or stored."""
    _, teacher = _session()
    classroom = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()

    res = client.post(
        "/assignments",
        json={
            "classroom_id": classroom["id"],
            "title": "Контролно",
            "due_at": "2030-10-01T20:59:00.000Z",
        },
        headers=teacher,
    )

    assert res.status_code == 201, res.text
    assert res.json()["due_at"].startswith("2030-10-01T20:59")


def test_a_student_cannot_read_the_teacher_report():
    _, teacher = _session()
    _, student = _session()
    classroom = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": classroom["join_code"]}, headers=student)
    assignment = client.post(
        "/assignments",
        json={"classroom_id": classroom["id"], "title": "Контролно"},
        headers=teacher,
    ).json()

    assert client.get(f"/assignments/{assignment['id']}", headers=student).status_code == 404
