"""The shared DB-backed store behind analytics/bug-report/feedback/error logs.

RELIABILITY: all four used to append to backend/logs/*.jsonl — a directory
inside the deployment bundle, read-only on Vercel. Every write there silently
failed in production, and each caller's own `except OSError: return
{"success": False}` meant that failure was never surfaced anywhere. This
store writes to the database instead, which is the only thing here that
actually persists on serverless.
"""
from app.models.event_log import EventLog
from app.services.event_log_store import append_log, read_recent


def test_append_log_persists_a_row(db):
    ok = append_log("analytics", {"event_type": "login", "user_id": "42"})

    assert ok is True
    row = db.query(EventLog).filter(EventLog.log_type == "analytics").order_by(EventLog.id.desc()).first()
    assert row is not None
    assert '"event_type": "login"' in row.payload_json


def test_read_recent_returns_newest_first(db):
    for i in range(3):
        append_log("bug_report_test", {"n": i})

    items = read_recent("bug_report_test", limit=10)

    assert [item["n"] for item in items] == [2, 1, 0]


def test_read_recent_only_returns_matching_log_type(db):
    append_log("feedback_test_a", {"marker": "a"})
    append_log("feedback_test_b", {"marker": "b"})

    items = read_recent("feedback_test_a", limit=10)

    assert len(items) == 1
    assert items[0]["marker"] == "a"


def test_read_recent_respects_the_limit(db):
    for i in range(5):
        append_log("limit_test", {"n": i})

    items = read_recent("limit_test", limit=2)

    assert len(items) == 2
    assert [item["n"] for item in items] == [4, 3]


def test_read_recent_is_empty_for_an_unknown_type():
    assert read_recent("never-written-to", limit=10) == []
