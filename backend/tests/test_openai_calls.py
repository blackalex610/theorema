"""OpenAI calls are time-bounded and never run on the event loop.

Every call site used to build its own client with no timeout — the SDK
default of 600s per attempt, retried twice — and call it synchronously from
inside `async def` endpoints. One slow completion then froze every other
request the process was serving, and on Vercel ran into the function limit.
"""
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import nvo as nvo_module
from app.routers.nvo import NVOExam, NVOExamSubmitRequest, NVOQuestion, _store_exam, submit_nvo_exam
from app.services import openai_client as client_module
from app.services.openai_client import openai_client


@pytest.fixture(autouse=True)
def _fresh_clients():
    client_module._build.cache_clear()
    yield
    client_module._build.cache_clear()


# ─── The shared client ───────────────────────────────────────────────────────

def test_the_client_takes_its_timeout_and_retries_from_settings(monkeypatch):
    monkeypatch.setattr(client_module.settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(client_module.settings, "OPENAI_TIMEOUT_SECONDS", 12.5)
    monkeypatch.setattr(client_module.settings, "OPENAI_MAX_RETRIES", 1)
    client = openai_client()
    assert client.timeout == 12.5
    assert client.max_retries == 1


def test_a_long_job_can_ask_for_a_longer_timeout(monkeypatch):
    monkeypatch.setattr(client_module.settings, "OPENAI_API_KEY", "sk-test")
    assert openai_client(timeout=75).timeout == 75


def test_the_client_is_reused_not_rebuilt_per_call(monkeypatch):
    """A client per call threw away the connection pool every time."""
    monkeypatch.setattr(client_module.settings, "OPENAI_API_KEY", "sk-test")
    assert openai_client() is openai_client()


def test_a_base_url_routes_to_another_compatible_provider(monkeypatch):
    monkeypatch.setattr(client_module.settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(client_module.settings, "OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    assert str(openai_client().base_url).startswith("https://openrouter.ai/api/v1")


def test_no_module_builds_its_own_client():
    """Anything constructing OpenAI(...) directly escapes the timeout policy."""
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if path.name != "openai_client.py" and "OpenAI(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ─── Off the event loop ──────────────────────────────────────────────────────

def test_chat_runs_the_model_call_off_the_event_loop(monkeypatch):
    import app.routers.ai_chat as ai_chat

    seen = {}

    def fake_reply(**kwargs):
        seen["thread"] = threading.current_thread()
        return "здравей"

    monkeypatch.setattr(ai_chat, "generate_chat_reply", fake_reply)
    headers = {"Authorization": f"Bearer {TestClient(app).post('/auth/guest', headers={'X-Forwarded-For': '203.0.113.77'}).json()['access_token']}"}
    res = TestClient(app).post("/ai/chat", headers=headers, json={"messages": [{"role": "user", "content": "здр"}]})
    assert res.status_code == 200, res.text
    assert seen["thread"] is not threading.main_thread()
    assert "AnyIO worker thread" in seen["thread"].name


def _written(number: int) -> NVOQuestion:
    return NVOQuestion(
        number=number,
        question=f"Written {number}",
        topic="general",
        difficulty="hard",
        diagram=False,
        options=None,
        open_parts=None,
        correct_answer=f"key {number}",
    )


def test_submit_grades_written_answers_concurrently(monkeypatch, db, make_user):
    """Three written answers used to mean three model calls back to back.

    Each stub waits at a barrier that only opens once all three are in
    flight — so this passes only if they really run at the same time, and
    fails (BrokenBarrierError) if they run one after another.
    """
    barrier = threading.Barrier(3, timeout=5)

    def mark(**kwargs):
        barrier.wait()
        parts = kwargs["parts"]
        return [p["max_points"] for p in parts], ["ok" for _ in parts], "extracted"

    monkeypatch.setattr(nvo_module, "_ai_mark", mark)
    _store_exam(NVOExam(exam_id="concurrent01", questions=[_written(1), _written(2), _written(3)]))

    payload = NVOExamSubmitRequest(
        exam_id="concurrent01",
        answers={"1": "a wrong one", "2": "another", "3": "and a third"},
        open_answer_images=[],
        questions=[],
    )
    result = asyncio.run(submit_nvo_exam(payload, current_user=make_user(), db=db))

    assert [r.problemId for r in result.open_results] == [1, 2, 3], "results keep question order"
    assert all(r.score == r.max_score for r in result.open_results)


def test_one_failed_grade_is_a_502_not_a_partial_result(monkeypatch, db, make_user):
    """A model failure is absorbed inside grade_written (the answer is marked
    without it); anything that escapes grade_written must fail the submit
    rather than save a result with a hole in it."""
    real = nvo_module.grade_written

    def grade(**kwargs):
        if kwargs["statement"].endswith("2"):
            raise RuntimeError("grader bug")
        return real(**kwargs)

    def mark(**kwargs):
        parts = kwargs["parts"]
        return [p["max_points"] for p in parts], ["ok" for _ in parts], "extracted"

    monkeypatch.setattr(nvo_module, "grade_written", grade)
    monkeypatch.setattr(nvo_module, "_ai_mark", mark)
    _store_exam(NVOExam(exam_id="concurrent02", questions=[_written(1), _written(2)]))

    payload = NVOExamSubmitRequest(
        exam_id="concurrent02", answers={"1": "x", "2": "y"}, open_answer_images=[], questions=[]
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        asyncio.run(submit_nvo_exam(payload, current_user=make_user(), db=db))
    assert caught.value.status_code == 502
