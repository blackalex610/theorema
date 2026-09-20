"""Saved problems: a student's bookmarked practice exercises and NVO questions."""
import json

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.saved_problem import SavedProblem


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
