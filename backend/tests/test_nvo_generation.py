"""Tests for the NVO generation pipeline fixes.

Two bugs made AI generation effectively dead in production:
  * the model wraps its JSON in ```json fences, which `json.loads` rejected —
    the caller swallowed the error and silently fell back to the catalog;
  * the short format skipped diagram injection, so a "16 question" short exam
    contained zero diagram questions.
"""
import json

import pytest

from app.routers.nvo import (
    _get_question_counts,
    _inject_playground_problems,
    _strip_json_fences,
)


# ─── Fenced JSON ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", [
    '{"questions": []}',
    '```json\n{"questions": []}\n```',
    '```\n{"questions": []}\n```',
    '  ```json\n{"questions": []}\n```  ',
    '```JSON\n{"questions": []}\n```',
])
def test_fenced_json_survives_the_round_trip(raw):
    assert json.loads(_strip_json_fences(raw)) == {"questions": []}


def test_stripping_leaves_clean_json_untouched():
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'


# ─── Question counts ─────────────────────────────────────────────────────────

def test_question_counts():
    assert _get_question_counts("short") == (15, 1)
    assert sum(_get_question_counts("short")) == 16
    assert _get_question_counts("full") == (20, 3)
    assert _get_question_counts(None) == (20, 3)


# ─── Playground/diagram injection ────────────────────────────────────────────

def _blank_questions(count: int) -> list:
    from app.routers.nvo import NVOQuestion

    return [
        NVOQuestion(
            number=i,
            question=f"placeholder {i}",
            topic="general",
            difficulty="medium",
            diagram=False,
            options=["А", "Б", "В", "Г"],
        )
        for i in range(1, count + 1)
    ]


@pytest.mark.parametrize("format,count", [("full", 23), (None, 23), ("short", 16)])
def test_injection_preserves_length_and_numbering(format, count):
    result = _inject_playground_problems(_blank_questions(count), format)

    assert len(result) == count
    assert [q.number for q in result] == list(range(1, count + 1))


@pytest.mark.parametrize("format,count", [("full", 23), ("short", 16)])
def test_injection_replaces_the_placeholder_questions(format, count):
    """Both formats must actually receive playground content, short included."""
    original = _blank_questions(count)
    result = _inject_playground_problems(original, format)

    replaced = [
        q.number for q, o in zip(result, original) if q.question != o.question
    ]
    # Q10-Q15 are the diagram MCQ slots in both formats.
    assert set(range(10, 16)).issubset(set(replaced))
    # ...plus the trailing open question (Q23 full / Q16 short).
    assert count in replaced


def test_short_format_keeps_its_open_question_last():
    """The MCQ loop must never overwrite the single short-format open slot."""
    result = _inject_playground_problems(_blank_questions(16), "short")
    assert result[-1].number == 16
    assert result[-1].options is None


# ─── Format-aware OpenAI prompt ──────────────────────────────────────────────
#
# The prompt used to hard-code "Exactly 23 questions" and a Q1-Q23 slot guide
# even when format="short". The model dutifully returned 23, the 16-question
# validation rejected it, and short-format AI generation could never succeed —
# every short exam silently came from the catalog fallback.

def _fake_openai(monkeypatch, captured: dict, response_text: str):
    """Replace nvo.OpenAI with a stub that records the request it was given."""
    from types import SimpleNamespace

    from app.routers import nvo as nvo_module

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=response_text))]
            )

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(nvo_module.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(nvo_module, "OpenAI", _FakeClient)


def _exam_payload(total: int, mcq: int) -> str:
    questions = []
    for number in range(1, total + 1):
        is_open = number > mcq
        questions.append({
            "number": number,
            "question": f"Задача {number}",
            "topic": "general",
            "difficulty": "medium",
            "diagram": False,
            "options": None if is_open else ["А", "Б", "В", "Г"],
            "open_parts": ["а)", "б)"] if is_open else None,
        })
    return json.dumps({"questions": questions}, ensure_ascii=False)


@pytest.mark.parametrize("format,total,mcq", [("short", 16, 15), ("full", 23, 20), (None, 23, 20)])
def test_generation_asks_for_and_accepts_the_requested_format(monkeypatch, format, total, mcq):
    from app.routers.nvo import _generate_via_openai

    captured: dict = {}
    _fake_openai(monkeypatch, captured, _exam_payload(total, mcq))

    exam = _generate_via_openai(format=format)

    assert len(exam.questions) == total
    assert [q.number for q in exam.questions] == list(range(1, total + 1))

    prompt = captured["messages"][-1]["content"]
    assert f"Exactly {total} questions" in prompt
    assert f"Q1-Q{mcq}: multiple choice" in prompt
    # The slot guide must stop at the last real slot, not run to Q23 for short.
    assert f"Q{total} [" in prompt
    assert f"Q{total + 1} [" not in prompt


def test_generation_requests_json_object_response_format(monkeypatch):
    """Without response_format the model wraps JSON in fences and parsing dies."""
    from app.routers.nvo import _generate_via_openai

    captured: dict = {}
    _fake_openai(monkeypatch, captured, _exam_payload(23, 20))

    _generate_via_openai()

    assert captured["response_format"] == {"type": "json_object"}


def test_generation_still_parses_a_fenced_response(monkeypatch):
    from app.routers.nvo import _generate_via_openai

    captured: dict = {}
    _fake_openai(monkeypatch, captured, f"```json\n{_exam_payload(16, 15)}\n```")

    assert len(_generate_via_openai(format="short").questions) == 16


def test_generation_rejects_a_wrong_length_response(monkeypatch):
    from fastapi import HTTPException

    from app.routers.nvo import _generate_via_openai

    captured: dict = {}
    _fake_openai(monkeypatch, captured, _exam_payload(23, 20))

    with pytest.raises(HTTPException) as exc:
        _generate_via_openai(format="short")
    assert exc.value.status_code == 502


# ─── Generated exams must outlive the process that made them ─────────────────
#
# GENERATED_EXAMS was a module-level dict. On serverless the request that
# generated an exam and the request that fetched it can hit different
# instances, so /nvo/generated/{id} 404'd an exam that had just succeeded.
# clear_cache() below is that cold start.

def _sample_exam(exam_id: str = "coldstrt"):
    from app.routers.nvo import NVOExam

    return NVOExam(exam_id=exam_id, questions=_blank_questions(3))


def test_generated_exam_endpoint_survives_a_cold_start():
    import asyncio

    from app.routers.nvo import _store_exam, get_generated_nvo_exam
    from app.services.nvo_exam_store import clear_cache

    _store_exam(_sample_exam())
    clear_cache()

    exam = asyncio.run(get_generated_nvo_exam("coldstrt"))
    assert exam.exam_id == "coldstrt"
    assert [q.number for q in exam.questions] == [1, 2, 3]


def test_generated_exam_endpoint_still_404s_for_an_unknown_id():
    import asyncio

    from fastapi import HTTPException

    from app.routers.nvo import get_generated_nvo_exam
    from app.services.nvo_exam_store import clear_cache

    clear_cache()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_generated_nvo_exam("no-such-id"))
    assert exc.value.status_code == 404


def test_generation_job_status_survives_a_cold_start():
    import asyncio

    from app.routers.nvo import _set_job_progress, get_nvo_generation_job
    from app.services.nvo_exam_store import clear_cache

    _set_job_progress(
        "coldjob1",
        status="completed",
        progress=100,
        message="Тестът е готов",
        exam_id="coldstrt",
    )
    clear_cache()

    job = asyncio.run(get_nvo_generation_job("coldjob1"))
    assert job.status == "completed"
    assert job.progress == 100
    assert job.exam_id == "coldstrt"


def test_a_stored_exam_is_graded_from_the_server_copy_not_the_client_payload():
    """/nvo/submit must be able to find the exam without the client resending it."""
    from app.routers.nvo import _load_exam, _store_exam
    from app.services.nvo_exam_store import clear_cache

    _store_exam(_sample_exam("submit01"))
    clear_cache()

    assert _load_exam("submit01") is not None


# ─── /nvo/generate-job must not block the request on generation ─────────────
#
# create_nvo_generation_job used to `await loop.run_in_executor(...)` the
# entire generation inline, so the request blocked for as long as generation
# took (up to the 75s OpenAI timeout) despite the job/polling shape already
# existing on both sides — GET /nvo/generate-job/{id} existed purely to poll
# a job that, in practice, was already finished by the time the client had
# the job_id to poll with. Separately, the daily nvo_exams credit used to be
# charged by the require_nvo_exam dependency before generation ran at all, so
# a failed generation cost the credit for nothing.

def test_generate_job_returns_immediately_as_queued(db, make_user):
    import asyncio

    from fastapi import BackgroundTasks
    from app.routers.nvo import create_nvo_generation_job

    user = make_user()
    background_tasks = BackgroundTasks()

    job = asyncio.run(create_nvo_generation_job(background_tasks, request=None, current_user=user))

    assert job.status == "queued"
    assert job.progress == 0
    assert len(background_tasks.tasks) == 1  # the actual work has not run yet


def test_generate_job_does_not_charge_the_credit_before_the_background_task_runs(db, make_user):
    import asyncio

    from fastapi import BackgroundTasks
    from app.routers.nvo import create_nvo_generation_job

    user = make_user()
    before = user.nvo_exams_today
    background_tasks = BackgroundTasks()

    asyncio.run(create_nvo_generation_job(background_tasks, request=None, current_user=user))

    db.refresh(user)
    assert user.nvo_exams_today == before  # unchanged until the job actually succeeds


def test_generate_job_charges_the_credit_once_the_background_task_succeeds(monkeypatch, db, make_user):
    import asyncio

    from fastapi import BackgroundTasks
    from app.routers.nvo import create_nvo_generation_job, get_nvo_generation_job
    import app.routers.nvo as nvo_module

    monkeypatch.setattr(nvo_module.settings, "OPENAI_API_KEY", "")  # forces the pool fallback
    user = make_user()
    before = user.nvo_exams_today
    background_tasks = BackgroundTasks()

    job = asyncio.run(create_nvo_generation_job(background_tasks, request=None, current_user=user))
    asyncio.run(background_tasks())  # simulate Starlette running it after the response is sent

    completed = asyncio.run(get_nvo_generation_job(job.job_id))
    assert completed.status == "completed"

    db.refresh(user)
    assert user.nvo_exams_today == before + 1


def test_generate_job_does_not_charge_the_credit_when_generation_fails(monkeypatch, db, make_user):
    import asyncio

    from fastapi import BackgroundTasks, HTTPException
    from app.routers.nvo import create_nvo_generation_job, get_nvo_generation_job
    import app.routers.nvo as nvo_module

    def _boom(*args, **kwargs):
        raise HTTPException(status_code=500, detail="boom")

    # Every generation path has to fail for the job to fail. The blueprint
    # generator was added in front of these two and succeeds offline, so
    # patching only the original pair no longer tests anything.
    monkeypatch.setattr(nvo_module, "_generate_via_blueprint", _boom)
    monkeypatch.setattr(nvo_module, "_generate_via_openai", _boom)
    monkeypatch.setattr(nvo_module, "_fallback_generate_from_pool", _boom)
    user = make_user()
    before = user.nvo_exams_today
    background_tasks = BackgroundTasks()

    job = asyncio.run(create_nvo_generation_job(background_tasks, request=None, current_user=user))
    asyncio.run(background_tasks())

    completed = asyncio.run(get_nvo_generation_job(job.job_id))
    assert completed.status == "failed"

    db.refresh(user)
    assert user.nvo_exams_today == before  # never charged for a failed generation


