"""Sentry forwarding for frontend error reports.

SENTRY_DSN is empty by default (see app/config.py) — these tests pin that
append_error_log never touches sentry_sdk in that state (no import error, no
network attempt), and that when a DSN *is* configured, the report is
forwarded as a Sentry event without ever raising back into the request path.
"""
from app.services import error_logger


def test_forward_to_sentry_is_a_no_op_without_a_dsn(monkeypatch):
    monkeypatch.setattr(error_logger.settings, "SENTRY_DSN", "")

    import sentry_sdk

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda msg, level: captured.append((msg, level)))

    error_logger._forward_to_sentry({"message": "boom", "level": "error"})

    assert captured == []  # never called sentry_sdk at all


def test_forward_to_sentry_sends_a_capture_message_when_a_dsn_is_set(monkeypatch):
    monkeypatch.setattr(error_logger.settings, "SENTRY_DSN", "https://fake@o0.ingest.sentry.io/1")

    import sentry_sdk

    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda msg, level: captured.append((msg, level)))

    error_logger._forward_to_sentry({"message": "Something broke", "level": "warning", "route": "/x"})

    assert captured == [("Something broke", "warning")]


def test_forward_to_sentry_never_raises_even_if_sentry_itself_errors(monkeypatch):
    """A Sentry-side failure must not turn a client's error report into a 500
    of its own — /log-error's whole point is to survive things going wrong.
    """
    monkeypatch.setattr(error_logger.settings, "SENTRY_DSN", "https://fake@o0.ingest.sentry.io/1")

    import sentry_sdk

    def _raise(*args, **kwargs):
        raise RuntimeError("network is down")

    monkeypatch.setattr(sentry_sdk, "capture_message", _raise)

    error_logger._forward_to_sentry({"message": "boom", "level": "error"})  # must not raise


def test_append_error_log_still_persists_when_sentry_forwarding_is_configured(db, monkeypatch):
    """The event_logs write must not depend on Sentry being reachable."""
    monkeypatch.setattr(error_logger.settings, "SENTRY_DSN", "https://fake@o0.ingest.sentry.io/1")

    import sentry_sdk
    monkeypatch.setattr(sentry_sdk, "capture_message", lambda *a, **k: None)

    error_logger.append_error_log({"message": "test entry", "level": "error", "timestamp": "now"})

    items = error_logger.read_recent_logs(limit=5)
    assert any(item.get("message") == "test entry" for item in items)
