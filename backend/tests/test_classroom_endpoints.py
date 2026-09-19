"""HTTP layer for classrooms.

The service tests cover the rules; these cover that the rules are actually
wired to routes, that every route requires a session, and — most importantly
— that one signed-in user cannot read another's class.
"""
import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.classroom import Classroom, ClassroomMember

client = TestClient(app)

_ip_counter = itertools.count()


def _session() -> tuple[int, dict]:
    res = client.post(
        "/auth/guest",
        headers={"X-Forwarded-For": f"192.0.2.{next(_ip_counter) % 254 + 1}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.query(ClassroomMember).delete(synchronize_session=False)
    db.query(Classroom).delete(synchronize_session=False)
    db.commit()


# ─── Auth ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("post", "/classrooms"),
    ("get", "/classrooms"),
    ("post", "/classrooms/join"),
    ("get", "/classrooms/mine"),
])
def test_every_classroom_route_requires_a_session(method, path):
    kwargs = {"json": {}} if method == "post" else {}
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 401, f"{method.upper()} {path} was reachable anonymously"


# ─── Teacher flow ────────────────────────────────────────────────────────────

def test_a_teacher_creates_a_class_and_gets_a_code():
    _, headers = _session()

    res = client.post("/classrooms", json={"name": "7А математика", "grade_level": 7}, headers=headers)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "7А математика"
    assert len(body["join_code"]) == 6
    assert body["student_count"] == 0


def test_a_class_needs_a_name():
    _, headers = _session()

    assert client.post("/classrooms", json={"name": "   "}, headers=headers).status_code == 422


def test_the_teacher_lists_their_classes():
    _, headers = _session()
    client.post("/classrooms", json={"name": "7А"}, headers=headers)
    client.post("/classrooms", json={"name": "7Б"}, headers=headers)

    res = client.get("/classrooms", headers=headers)

    assert res.status_code == 200
    assert sorted(c["name"] for c in res.json()["classrooms"]) == ["7А", "7Б"]


def test_one_teacher_cannot_see_anothers_class():
    _, teacher = _session()
    _, intruder = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()

    res = client.get(f"/classrooms/{created['id']}", headers=intruder)

    assert res.status_code == 404


# ─── Student flow ────────────────────────────────────────────────────────────

def test_a_student_joins_and_then_appears_on_the_roster():
    _, teacher = _session()
    student_id, student = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()

    joined = client.post("/classrooms/join", json={"join_code": created["join_code"]}, headers=student)
    assert joined.status_code == 200, joined.text
    assert joined.json()["name"] == "7А"

    roster = client.get(f"/classrooms/{created['id']}", headers=teacher).json()
    assert [row["student_id"] for row in roster["roster"]] == [student_id]
    assert roster["student_count"] == 1


def test_a_bad_code_tells_the_student_so():
    _, student = _session()

    res = client.post("/classrooms/join", json={"join_code": "ZZZZZZ"}, headers=student)

    assert res.status_code == 404


def test_a_student_lists_and_leaves_their_classes():
    _, teacher = _session()
    _, student = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": created["join_code"]}, headers=student)

    mine = client.get("/classrooms/mine", headers=student).json()
    assert [c["name"] for c in mine["classrooms"]] == ["7А"]

    left = client.delete(f"/classrooms/{created['id']}/leave", headers=student)
    assert left.status_code == 200
    assert client.get("/classrooms/mine", headers=student).json()["classrooms"] == []


def test_a_teacher_removes_a_student():
    _, teacher = _session()
    student_id, student = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": created["join_code"]}, headers=student)

    res = client.delete(f"/classrooms/{created['id']}/members/{student_id}", headers=teacher)

    assert res.status_code == 200
    assert client.get(f"/classrooms/{created['id']}", headers=teacher).json()["roster"] == []


def test_a_stranger_cannot_remove_someone_elses_student():
    _, teacher = _session()
    student_id, student = _session()
    _, intruder = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()
    client.post("/classrooms/join", json={"join_code": created["join_code"]}, headers=student)

    res = client.delete(f"/classrooms/{created['id']}/members/{student_id}", headers=intruder)

    assert res.status_code == 404
    assert len(client.get(f"/classrooms/{created['id']}", headers=teacher).json()["roster"]) == 1


def test_archiving_stops_new_joins():
    _, teacher = _session()
    _, student = _session()
    created = client.post("/classrooms", json={"name": "7А"}, headers=teacher).json()

    assert client.post(f"/classrooms/{created['id']}/archive", headers=teacher).status_code == 200

    res = client.post("/classrooms/join", json={"join_code": created["join_code"]}, headers=student)
    assert res.status_code == 410
