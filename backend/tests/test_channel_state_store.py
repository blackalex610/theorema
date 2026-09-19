"""Durability of the desktop<->phone channel state.

The bug this store exists to fix is not a crash — it is that the two halves of
the pairing flow are requests from *different devices*, and on serverless they
land on different instances. The desktop registered a task context; the phone
graded against it and got 404. The phone uploaded a photo; the desktop polled
and saw nothing.

So the tests that matter here drop the in-process cache between the write and
the read (`_cold_instance`). That is what "a different instance serves this
request" looks like from inside a test, and it is exactly the case the old
module-level dicts failed.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.mobile_channel import MobileTaskContext, MobileUploadRecord
from app.services import channel_state_store as store


@pytest.fixture(autouse=True)
def _clean(db):
    """Drop rows and caches around each test."""
    def _wipe():
        db.query(MobileUploadRecord).delete()
        db.query(MobileTaskContext).delete()
        db.commit()
        store._uploads_cache.clear()
        store._contexts_cache.clear()

    _wipe()
    yield
    db.rollback()
    _wipe()


def _cold_instance():
    """Simulate the request being served by a process that never saw the write."""
    store._uploads_cache.clear()
    store._contexts_cache.clear()


def _event(name: str = "photo.jpg", **overrides) -> dict:
    return {
        "channel_id": "chan-abcdef12",
        "file_name": name,
        "file_url": f"/media/{name}",
        "content_type": "image/jpeg",
        "size_bytes": 1234,
        "uploaded_at": datetime.utcnow().isoformat(),
        "problem_number": 34,
        **overrides,
    }


def _context(problem_number: int = 34, **overrides) -> dict:
    return {
        "channel_id": "chan-abcdef12",
        "problem_number": problem_number,
        "a": 2,
        "b": 3,
        "correct_xy": "(1; 2)",
        "updated_at": datetime.utcnow().isoformat(),
        "statement": "Реши системата.",
        **overrides,
    }


# ─── Uploads ─────────────────────────────────────────────────────────────────

def test_an_upload_is_visible_to_an_instance_that_never_saw_it():
    """The original bug: the desktop polls a different instance than the phone wrote to."""
    store.record_upload("chan-abcdef12", _event(), 100)
    _cold_instance()

    (loaded,) = store.load_uploads("chan-abcdef12", 20)
    assert loaded["file_name"] == "photo.jpg"


def test_uploads_come_back_newest_first():
    for i in range(3):
        store.record_upload("chan-abcdef12", _event(f"p{i}.jpg"), 100)
    _cold_instance()

    names = [e["file_name"] for e in store.load_uploads("chan-abcdef12", 20)]
    assert names == ["p2.jpg", "p1.jpg", "p0.jpg"]


def test_history_is_capped_so_a_long_session_cannot_grow_without_limit():
    for i in range(10):
        store.record_upload("chan-abcdef12", _event(f"p{i}.jpg"), 3)
    _cold_instance()

    loaded = store.load_uploads("chan-abcdef12", 50)
    assert [e["file_name"] for e in loaded] == ["p9.jpg", "p8.jpg", "p7.jpg"]


def test_the_caller_limit_is_respected():
    for i in range(5):
        store.record_upload("chan-abcdef12", _event(f"p{i}.jpg"), 100)
    _cold_instance()

    assert len(store.load_uploads("chan-abcdef12", 2)) == 2


def test_channels_never_see_each_others_uploads():
    store.record_upload("chan-aaaaaaaa", _event("mine.jpg"), 100)
    store.record_upload("chan-bbbbbbbb", _event("theirs.jpg"), 100)
    _cold_instance()

    assert [e["file_name"] for e in store.load_uploads("chan-aaaaaaaa", 20)] == ["mine.jpg"]
    assert [e["file_name"] for e in store.load_uploads("chan-bbbbbbbb", 20)] == ["theirs.jpg"]


def test_an_unknown_channel_is_empty_not_an_error():
    assert store.load_uploads("chan-nothing", 20) == []


def test_clearing_history_removes_it_for_every_instance():
    store.record_upload("chan-abcdef12", _event(), 100)
    store.clear_uploads("chan-abcdef12")
    _cold_instance()

    assert store.load_uploads("chan-abcdef12", 20) == []


def test_expired_uploads_are_not_returned(db):
    store.record_upload("chan-abcdef12", _event(), 100)
    db.query(MobileUploadRecord).update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
    db.commit()
    _cold_instance()

    assert store.load_uploads("chan-abcdef12", 20) == []


# ─── Task contexts ───────────────────────────────────────────────────────────

def test_a_task_context_is_visible_to_an_instance_that_never_saw_it():
    """The original bug: /tasks/grade-photo 404s because it ran elsewhere."""
    store.save_task_context("chan-abcdef12", 34, _context())
    _cold_instance()

    loaded = store.load_task_context("chan-abcdef12", 34)
    assert loaded is not None
    assert loaded["correct_xy"] == "(1; 2)"
    assert loaded["statement"] == "Реши системата."


def test_re_registering_a_problem_replaces_its_answer_key():
    """Two live answer keys for one problem would let the grader pick either."""
    store.save_task_context("chan-abcdef12", 34, _context(correct_xy="(1; 2)"))
    store.save_task_context("chan-abcdef12", 34, _context(correct_xy="(9; 9)"))
    _cold_instance()

    loaded = store.load_task_context("chan-abcdef12", 34)
    assert loaded["correct_xy"] == "(9; 9)"
    assert len(store.load_task_contexts("chan-abcdef12")) == 1


def test_an_unregistered_problem_reads_as_none():
    store.save_task_context("chan-abcdef12", 34, _context())
    _cold_instance()

    assert store.load_task_context("chan-abcdef12", 35) is None


def test_contexts_are_listed_in_problem_order():
    for number in (35, 34):
        store.save_task_context("chan-abcdef12", number, _context(number))
    _cold_instance()

    assert [c["problem_number"] for c in store.load_task_contexts("chan-abcdef12")] == [34, 35]


def test_channels_never_see_each_others_answer_keys():
    store.save_task_context("chan-aaaaaaaa", 34, _context(correct_xy="mine"))
    store.save_task_context("chan-bbbbbbbb", 34, _context(correct_xy="theirs"))
    _cold_instance()

    assert store.load_task_context("chan-aaaaaaaa", 34)["correct_xy"] == "mine"
    assert store.load_task_context("chan-bbbbbbbb", 34)["correct_xy"] == "theirs"


def test_expired_contexts_are_not_returned(db):
    store.save_task_context("chan-abcdef12", 34, _context())
    db.query(MobileTaskContext).update({"expires_at": datetime.utcnow() - timedelta(seconds=1)})
    db.commit()
    _cold_instance()

    assert store.load_task_context("chan-abcdef12", 34) is None
    assert store.load_task_contexts("chan-abcdef12") == []


# ─── Failure policy ──────────────────────────────────────────────────────────
# Reads fall back to the cache; writes log and continue. A student who already
# uploaded a photo (and was already charged the scan credit) must not lose it
# to a database blip.

def _break_db(monkeypatch):
    class _Boom:
        def __getattr__(self, name):
            def _raise(*a, **kw):
                raise SQLAlchemyError("simulated outage")
            return _raise

    monkeypatch.setattr(store, "SessionLocal", lambda: _Boom())


def test_a_write_failure_is_logged_not_raised(monkeypatch, caplog):
    _break_db(monkeypatch)

    store.record_upload("chan-abcdef12", _event(), 100)      # must not raise
    store.save_task_context("chan-abcdef12", 34, _context())  # must not raise

    assert "Failed to persist" in caplog.text


def test_a_read_failure_falls_back_to_this_instances_cache(monkeypatch):
    store.record_upload("chan-abcdef12", _event(), 100)
    store.save_task_context("chan-abcdef12", 34, _context())
    _break_db(monkeypatch)

    # Same instance, so the cache still holds both — a database blip should not
    # 404 data this process is sitting on.
    assert len(store.load_uploads("chan-abcdef12", 20)) == 1
    assert store.load_task_context("chan-abcdef12", 34)["correct_xy"] == "(1; 2)"
    assert len(store.load_task_contexts("chan-abcdef12")) == 1


def test_a_read_failure_with_a_cold_cache_degrades_to_empty(monkeypatch):
    _break_db(monkeypatch)

    assert store.load_uploads("chan-abcdef12", 20) == []
    assert store.load_task_context("chan-abcdef12", 34) is None
    assert store.load_task_contexts("chan-abcdef12") == []


def test_corrupt_stored_json_is_skipped_rather_than_crashing(db, caplog):
    store.record_upload("chan-abcdef12", _event(), 100)
    store.save_task_context("chan-abcdef12", 34, _context())
    db.query(MobileUploadRecord).update({"payload_json": "{not json"})
    db.query(MobileTaskContext).update({"payload_json": "{not json"})
    db.commit()
    _cold_instance()

    assert store.load_uploads("chan-abcdef12", 20) == []
    assert store.load_task_context("chan-abcdef12", 34) is None
    assert store.load_task_contexts("chan-abcdef12") == []
    assert "not valid JSON" in caplog.text
