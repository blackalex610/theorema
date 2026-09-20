"""Saved problems: a student's bookmarked practice exercises and NVO questions."""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.saved_problem import SavedProblem
from app.services import saved_problems as svc


@pytest.fixture(autouse=True)
def _clean_saved_problems(db):
    """Delete every row before and after each test.

    No user_id column in this schema carries a foreign key, so make_user's
    teardown leaves child rows behind. SQLite then reuses ids, and the
    (user_id, source, source_ref) unique constraint fires on a row belonging
    to a long-gone user from an earlier test.
    """
    db.query(SavedProblem).delete()
    db.commit()
    yield
    db.query(SavedProblem).delete()
    db.commit()


def test_stores_a_snapshot_and_reads_it_back(db, make_user):
    user = make_user()
    snapshot = {"kind": "exercise", "question": "Колко е 2 + 2?", "answer_type": "numeric"}
    db.add(
        SavedProblem(
            user_id=user.id,
            source="exercise",
            source_ref="4271",
            snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        )
    )
    db.commit()

    row = db.query(SavedProblem).filter(SavedProblem.user_id == user.id).one()
    assert row.source == "exercise"
    assert row.source_ref == "4271"
    assert json.loads(row.snapshot_json)["question"] == "Колко е 2 + 2?"
    assert row.created_at is not None


def test_the_same_problem_cannot_be_saved_twice_by_one_user(db, make_user):
    user = make_user()
    for _ in range(2):
        db.add(
            SavedProblem(
                user_id=user.id, source="nvo", source_ref="exam-abc:7", snapshot_json="{}"
            )
        )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_two_students_may_each_save_the_same_problem(db, make_user):
    first, second = make_user(), make_user()
    for user in (first, second):
        db.add(
            SavedProblem(
                user_id=user.id, source="nvo", source_ref="exam-abc:7", snapshot_json="{}"
            )
        )
    db.commit()
    assert db.query(SavedProblem).filter(SavedProblem.source_ref == "exam-abc:7").count() == 2


# ─── Service layer ──────────────────────────────────────────────────────────

def _snapshot(question="Колко е 2 + 2?"):
    return {"kind": "exercise", "question": question, "answer_type": "numeric"}


def test_saving_returns_the_row_and_reports_it_as_created(db, make_user):
    user = make_user()
    row, created = svc.save_problem(
        db, user_id=user.id, source="exercise", source_ref="4271", snapshot=_snapshot()
    )
    assert created is True
    assert row.id is not None
    assert svc.snapshot_of(row)["question"] == "Колко е 2 + 2?"


def test_saving_the_same_problem_again_is_idempotent(db, make_user):
    user = make_user()
    first, created_first = svc.save_problem(
        db, user_id=user.id, source="exercise", source_ref="4271", snapshot=_snapshot()
    )
    second, created_second = svc.save_problem(
        db, user_id=user.id, source="exercise", source_ref="4271", snapshot=_snapshot("друго")
    )
    assert created_first is True
    assert created_second is False
    assert second.id == first.id
    assert db.query(SavedProblem).filter(SavedProblem.user_id == user.id).count() == 1


def test_rejects_an_unknown_source(db, make_user):
    user = make_user()
    with pytest.raises(HTTPException) as exc:
        svc.save_problem(
            db, user_id=user.id, source="homework", source_ref="1", snapshot=_snapshot()
        )
    assert exc.value.status_code == 400


def test_rejects_a_snapshot_without_a_question(db, make_user):
    user = make_user()
    with pytest.raises(HTTPException) as exc:
        svc.save_problem(
            db, user_id=user.id, source="exercise", source_ref="1", snapshot={"kind": "exercise"}
        )
    assert exc.value.status_code == 400


def test_rejects_a_save_past_the_cap(db, make_user):
    user = make_user()
    for index in range(svc.SAVED_PROBLEMS_MAX_PER_USER):
        db.add(
            SavedProblem(
                user_id=user.id,
                source="exercise",
                source_ref=str(index),
                snapshot_json="{}",
            )
        )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        svc.save_problem(
            db, user_id=user.id, source="exercise", source_ref="over", snapshot=_snapshot()
        )
    assert exc.value.status_code == 409


def test_re_saving_at_the_cap_still_works(db, make_user):
    """The cap must not lock a student out of toggling something already saved."""
    user = make_user()
    for index in range(svc.SAVED_PROBLEMS_MAX_PER_USER):
        db.add(
            SavedProblem(
                user_id=user.id, source="exercise", source_ref=str(index), snapshot_json="{}"
            )
        )
    db.commit()

    row, created = svc.save_problem(
        db, user_id=user.id, source="exercise", source_ref="0", snapshot=_snapshot()
    )
    assert created is False
    assert row.source_ref == "0"


def test_lists_newest_first(db, make_user):
    user = make_user()
    for ref in ("1", "2", "3"):
        svc.save_problem(
            db, user_id=user.id, source="exercise", source_ref=ref, snapshot=_snapshot()
        )
    rows = svc.list_problems(db, user_id=user.id, limit=10)
    assert [row.source_ref for row in rows] == ["3", "2", "1"]


def test_filters_by_source(db, make_user):
    user = make_user()
    svc.save_problem(db, user_id=user.id, source="exercise", source_ref="1", snapshot=_snapshot())
    svc.save_problem(db, user_id=user.id, source="nvo", source_ref="e:7", snapshot=_snapshot())

    assert len(svc.list_problems(db, user_id=user.id, limit=10, source="nvo")) == 1
    assert len(svc.list_problems(db, user_id=user.id, limit=10)) == 2


def test_never_leaks_another_students_saved_problems(db, make_user):
    mine, theirs = make_user(), make_user()
    svc.save_problem(db, user_id=mine.id, source="exercise", source_ref="1", snapshot=_snapshot())
    svc.save_problem(db, user_id=theirs.id, source="exercise", source_ref="2", snapshot=_snapshot())

    rows = svc.list_problems(db, user_id=mine.id, limit=10)
    assert [row.source_ref for row in rows] == ["1"]
    assert svc.list_refs(db, user_id=mine.id) == {"exercise:1": rows[0].id}


def test_refs_map_ref_keys_to_row_ids(db, make_user):
    user = make_user()
    row, _ = svc.save_problem(
        db, user_id=user.id, source="nvo", source_ref="exam-abc:7", snapshot=_snapshot()
    )
    assert svc.list_refs(db, user_id=user.id) == {"nvo:exam-abc:7": row.id}


def test_limit_is_clamped_by_the_service(db, make_user):
    user = make_user()
    for ref in range(3):
        svc.save_problem(
            db, user_id=user.id, source="exercise", source_ref=str(ref), snapshot=_snapshot()
        )
    assert len(svc.list_problems(db, user_id=user.id, limit=0)) == 1
    assert len(svc.list_problems(db, user_id=user.id, limit=9999)) == 3


def test_deletes_own_saved_problem(db, make_user):
    user = make_user()
    row, _ = svc.save_problem(
        db, user_id=user.id, source="exercise", source_ref="1", snapshot=_snapshot()
    )
    svc.delete_problem(db, user_id=user.id, saved_id=row.id)
    assert db.query(SavedProblem).filter(SavedProblem.user_id == user.id).count() == 0


def test_deleting_someone_elses_saved_problem_is_a_404(db, make_user):
    mine, theirs = make_user(), make_user()
    row, _ = svc.save_problem(
        db, user_id=theirs.id, source="exercise", source_ref="1", snapshot=_snapshot()
    )
    with pytest.raises(HTTPException) as exc:
        svc.delete_problem(db, user_id=mine.id, saved_id=row.id)
    assert exc.value.status_code == 404
    assert db.query(SavedProblem).filter(SavedProblem.id == row.id).count() == 1
