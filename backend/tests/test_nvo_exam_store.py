"""Tests for the durable generated-exam store.

Generated exams and generation jobs used to live in module-level dicts. On
serverless every request can hit a fresh process, so the exam a user had just
generated 404'd the moment their next request landed on another instance.

`clear_cache()` simulates exactly that cold start: it drops the in-process
cache and leaves only the database, which is the thing that has to work.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.nvo_exam import GeneratedExam, NVOGenerationJob
from app.services import nvo_exam_store
from app.services.nvo_exam_store import (
    clear_cache,
    load_exam,
    load_job,
    save_exam,
    save_job,
)


@pytest.fixture(autouse=True)
def _clean_store(db):
    clear_cache()
    db.query(GeneratedExam).delete()
    db.query(NVOGenerationJob).delete()
    db.commit()
    yield
    clear_cache()
    db.query(GeneratedExam).delete()
    db.query(NVOGenerationJob).delete()
    db.commit()


def _exam(exam_id: str = "abc12345", count: int = 3) -> dict:
    return {
        "exam_id": exam_id,
        "questions": [
            {
                "number": n,
                "question": f"Задача {n} — колко е $\\frac{{1}}{{2}}$?",
                "topic": "fractions",
                "difficulty": "medium",
                "diagram": False,
                "options": ["А", "Б", "В", "Г"],
                "correct_answer": "Б",
            }
            for n in range(1, count + 1)
        ],
    }


# ─── The cold-start regression ───────────────────────────────────────────────

def test_a_saved_exam_survives_a_cold_start():
    """The whole point: no in-process state, exam still resolves."""
    save_exam("abc12345", _exam())
    clear_cache()

    loaded = load_exam("abc12345")
    assert loaded is not None
    assert loaded["exam_id"] == "abc12345"
    assert len(loaded["questions"]) == 3


def test_a_saved_job_survives_a_cold_start():
    save_job("job00001", {
        "job_id": "job00001",
        "status": "completed",
        "progress": 100,
        "message": "Тестът е готов",
        "exam_id": "abc12345",
    })
    clear_cache()

    loaded = load_job("job00001")
    assert loaded == {
        "job_id": "job00001",
        "status": "completed",
        "progress": 100,
        "message": "Тестът е готов",
        "exam_id": "abc12345",
    }


def test_cyrillic_and_latex_round_trip_intact():
    """JSON serialisation must not mangle the Bulgarian text or the KaTeX."""
    save_exam("abc12345", _exam())
    clear_cache()

    question = load_exam("abc12345")["questions"][0]["question"]
    assert "Задача 1" in question
    assert "\\frac{1}{2}" in question


# ─── Misses ──────────────────────────────────────────────────────────────────

def test_an_unknown_exam_is_a_miss():
    assert load_exam("nope0000") is None


def test_an_unknown_job_is_a_miss():
    assert load_job("nope0000") is None


def test_an_expired_exam_is_not_served(db):
    save_exam("abc12345", _exam())
    db.query(GeneratedExam).filter(GeneratedExam.exam_id == "abc12345").update(
        {"expires_at": datetime.utcnow() - timedelta(seconds=1)}
    )
    db.commit()
    clear_cache()

    assert load_exam("abc12345") is None


def test_an_expired_cache_entry_is_not_served(monkeypatch):
    """Expiry is enforced on the cache too, not only on the database row."""
    monkeypatch.setattr(nvo_exam_store, "EXAM_TTL", timedelta(seconds=-1))
    save_exam("abc12345", _exam())

    assert load_exam("abc12345") is None


def test_saving_again_overwrites_rather_than_duplicating(db):
    save_exam("abc12345", _exam(count=3))
    save_exam("abc12345", _exam(count=5))
    clear_cache()

    assert db.query(GeneratedExam).filter(GeneratedExam.exam_id == "abc12345").count() == 1
    assert len(load_exam("abc12345")["questions"]) == 5


# ─── Housekeeping ────────────────────────────────────────────────────────────

def test_expired_rows_are_purged_on_write(db):
    db.add(GeneratedExam(
        exam_id="oldexam0",
        questions_json="{}",
        created_at=datetime.utcnow() - timedelta(days=3),
        expires_at=datetime.utcnow() - timedelta(days=2),
    ))
    db.commit()

    save_exam("abc12345", _exam())

    assert db.query(GeneratedExam).filter(GeneratedExam.exam_id == "oldexam0").count() == 0


def test_the_hot_cache_stays_bounded():
    """A long-lived process must not accumulate every exam it ever generated.

    Exercises the cache directly — the database round trip is irrelevant here
    and makes the test 100x slower.
    """
    cache: dict = {}
    expires_at = datetime.utcnow() + timedelta(hours=1)
    for i in range(nvo_exam_store._MAX_CACHED + 40):
        nvo_exam_store._cache_put(cache, f"exam{i:04d}", expires_at, {"exam_id": f"exam{i:04d}"})

    assert len(cache) == nvo_exam_store._MAX_CACHED
    # The most recent writes are the ones worth keeping.
    assert f"exam{nvo_exam_store._MAX_CACHED + 39:04d}" in cache


def test_expired_cache_entries_are_evicted_before_live_ones():
    cache: dict = {}
    past = datetime.utcnow() - timedelta(hours=1)
    future = datetime.utcnow() + timedelta(hours=1)
    for i in range(nvo_exam_store._MAX_CACHED):
        nvo_exam_store._cache_put(cache, f"dead{i:04d}", past, {})
    nvo_exam_store._cache_put(cache, "alive", future, {"exam_id": "alive"})

    assert "alive" in cache
    assert len(cache) <= nvo_exam_store._MAX_CACHED


# ─── Failure policy ──────────────────────────────────────────────────────────

def test_a_database_write_failure_is_logged_but_does_not_kill_the_request(monkeypatch, caplog):
    """Losing persistence must not throw away a generation run that already paid
    for its OpenAI call — but it must be loud in the log."""
    class _Boom:
        def __getattr__(self, name):
            def _raise(*args, **kwargs):
                raise SQLAlchemyError("database is locked")
            return _raise

    monkeypatch.setattr(nvo_exam_store, "SessionLocal", lambda: _Boom())

    with caplog.at_level("ERROR"):
        save_exam("abc12345", _exam())

    assert any("Failed to persist" in record.message for record in caplog.records)


def test_a_database_read_failure_falls_back_to_the_hot_cache(monkeypatch):
    save_exam("abc12345", _exam())

    class _Boom:
        def __getattr__(self, name):
            def _raise(*args, **kwargs):
                raise SQLAlchemyError("database is locked")
            return _raise

    monkeypatch.setattr(nvo_exam_store, "SessionLocal", lambda: _Boom())

    # Still cached in this process, so the miss never reaches the database.
    assert load_exam("abc12345") is not None
