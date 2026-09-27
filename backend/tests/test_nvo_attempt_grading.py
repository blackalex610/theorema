"""Server-side NVO scoring: the "make the numbers real" fix.

Before this, the exam a client received carried every `correct_answer`, MCQ
grading happened entirely in the browser, and /nvo/award-xp accepted
`percentage_correct` and `difficulty` as plain numbers in the request body —
so any signed-in caller could award themselves the maximum XP on repeat, and
`GET /nvo/questions` handed out the whole answer key with no auth at all.

Now:
  * the exam a client fetches never carries an answer key (_strip_answer_key)
  * /nvo/submit grades every question — MCQ included — against the server's
    own stored copy, and refuses to grade against a client-supplied fallback
  * /nvo/submit writes an NvoAttempt row; /nvo/award-xp reads it back instead
    of trusting the request, and is idempotent per attempt
  * /nvo/questions (the whole catalog, answers included) requires admin
"""
import asyncio
import json

import pytest
from fastapi import HTTPException

from app.routers.nvo import (
    NVOExam,
    NVOExamSubmitRequest,
    NVOAwardXpRequest,
    NVOOpenImageSubmission,
    NVOQuestion,
    _normalize_option_key,
    _store_exam,
    _strip_answer_key,
    award_nvo_exam_xp,
    generate_nvo_exam,
    get_generated_nvo_exam,
    get_nvo_questions,
    submit_nvo_exam,
)
from app.models.nvo_exam import NvoAttempt


# ─── _normalize_option_key ───────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    ("А", "А"),      # Cyrillic А, already correct
    ("A", "А"),      # Latin A must match its Cyrillic look-alike
    ("a", "А"),
    (" Б ", "Б"),    # whitespace tolerated
    ("в", "В"),
    ("Г) нещо", "Г"),  # a full option string, not just the bare key
    ("", ""),
    (None, ""),
])
def test_normalize_option_key(value, expected):
    assert _normalize_option_key(value) == expected


# ─── Exam fixtures ────────────────────────────────────────────────────────────

def _mcq(number: int, correct: str) -> NVOQuestion:
    return NVOQuestion(
        number=number,
        question=f"MCQ {number}",
        topic="general",
        difficulty="easy",
        diagram=False,
        options=["А) x", "Б) y", "В) z", "Г) w"],
        correct_answer=correct,
    )


def _open(number: int, correct: str) -> NVOQuestion:
    return NVOQuestion(
        number=number,
        question=f"Open {number}",
        topic="general",
        difficulty="hard",
        diagram=False,
        options=None,
        open_parts=None,
        correct_answer=correct,
    )


def _sample_exam(exam_id: str, difficulty: str = "standard", format: str = "full") -> NVOExam:
    return NVOExam(
        exam_id=exam_id,
        questions=[_mcq(1, "А"), _mcq(2, "В"), _open(3, "answer three")],
        difficulty=difficulty,
        format=format,
    )


def _fake_ai_grade(monkeypatch, *, is_correct: bool):
    """Stub the AI examiner so open-question tests don't hit OpenAI: full marks
    on every sub-part it is asked about, or none."""
    import app.routers.nvo as nvo_module

    def mark(**kwargs):
        parts = kwargs["parts"]
        return ([p["max_points"] if is_correct else 0 for p in parts],
                ["feedback" for _ in parts], "extracted")

    monkeypatch.setattr(nvo_module, "_ai_mark", mark)


def _submit(exam_id: str, answers: dict, user, db) -> "object":
    payload = NVOExamSubmitRequest(
        exam_id=exam_id,
        answers=answers,
        open_answer_images=[],
    )
    return asyncio.run(submit_nvo_exam(payload, current_user=user, db=db))


# ─── Answer key never reaches the client ──────────────────────────────────────

def test_generate_endpoint_strips_the_answer_key(monkeypatch, db, make_user):
    """POST /nvo/generate must never hand out correct_answer."""
    import app.routers.nvo as nvo_module

    monkeypatch.setattr(nvo_module.settings, "OPENROUTER_API_KEY", "")  # forces the pool fallback
    user = make_user()

    exam = asyncio.run(generate_nvo_exam(request=None, current_user=user, db=db))

    assert len(exam.questions) > 0
    assert all(q.correct_answer is None for q in exam.questions)


def test_generate_endpoint_charges_the_credit_only_after_success(monkeypatch, db, make_user):
    """The daily nvo_exams credit used to be spent by the require_nvo_exam
    dependency before generation ran at all; it is now charged only once an
    exam has actually been produced.
    """
    import app.routers.nvo as nvo_module

    monkeypatch.setattr(nvo_module.settings, "OPENROUTER_API_KEY", "")  # forces the pool fallback
    user = make_user()
    before = user.nvo_exams_today

    asyncio.run(generate_nvo_exam(request=None, current_user=user, db=db))

    db.refresh(user)
    assert user.nvo_exams_today == before + 1


def test_generated_exam_endpoint_strips_the_answer_key():
    """GET /nvo/generated/{exam_id} must not leak the stored answer key either."""
    from app.services.nvo_exam_store import clear_cache

    _store_exam(_sample_exam("strip001"))
    clear_cache()

    exam = asyncio.run(get_generated_nvo_exam("strip001"))

    assert all(q.correct_answer is None for q in exam.questions)


def test_strip_answer_key_does_not_mutate_the_original():
    original = _sample_exam("keep001")
    redacted = _strip_answer_key(original)

    assert all(q.correct_answer is None for q in redacted.questions)
    assert original.questions[0].correct_answer == "А"  # untouched


def test_questions_catalog_endpoint_takes_an_admin_dependency():
    """GET /nvo/questions returns the whole answer key with no per-question
    redaction — it must require an admin, not just any signed-in user. The
    route-wiring assertion (that FastAPI actually enforces this on the live
    route) lives in test_route_auth_matrix.py's ADMIN_ROUTES; this pins the
    function signature itself so the dependency can't be quietly dropped.
    """
    import inspect
    from app.auth.dependencies import require_admin

    params = inspect.signature(get_nvo_questions).parameters
    assert "_admin" in params
    assert params["_admin"].default.dependency is require_admin


# ─── /nvo/submit: server-side grading ────────────────────────────────────────

def test_submit_rejects_an_unknown_exam_even_with_a_client_supplied_answer_key(db, make_user):
    """The old fallback trusted payload.questions (client-supplied, including
    correct_answer) whenever the server had no record of the exam. That let
    an attacker submit a fabricated exam_id plus a self-chosen answer key and
    get it graded as if it were real. Now an unknown exam is just a 404.
    """
    user = make_user()
    payload = NVOExamSubmitRequest(
        exam_id="does-not-exist",
        answers={"1": "А"},
        open_answer_images=[],
        questions=[_mcq(1, "А")],  # attacker-supplied, must be ignored
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(submit_nvo_exam(payload, current_user=user, db=db))
    assert exc.value.status_code == 404


def test_submit_grades_mcq_server_side_against_the_stored_answer(db, make_user, monkeypatch):
    """The client cannot influence MCQ correctness — it can only report which
    option it picked, and the server checks that against its own stored copy.
    """
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("grade001"))

    result = _submit(
        "grade001",
        {"1": "А", "2": "Г", "3": "irrelevant, AI grader is stubbed"},  # Q1 right, Q2 wrong
        user, db,
    )

    assert result.mcq_score == 1
    assert result.mcq_max_score == 2


def test_submit_option_key_matching_is_case_and_script_tolerant(db, make_user, monkeypatch):
    """A Latin 'A' or lowercase letter from the client must still match the
    Cyrillic correct_answer stored server-side.
    """
    _fake_ai_grade(monkeypatch, is_correct=False)
    user = make_user()
    _store_exam(_sample_exam("grade002"))

    result = _submit("grade002", {"1": "A", "2": "в"}, user, db)  # Latin A; lowercase в

    assert result.mcq_score == 2  # both should match their Cyrillic correct_answer


def test_submit_ignores_a_client_supplied_correct_answer_for_scoring(db, make_user, monkeypatch):
    """Even if the client's `questions` payload lies about correct_answer, the
    server grades against its own stored exam, not the client's claim.
    """
    _fake_ai_grade(monkeypatch, is_correct=False)
    user = make_user()
    _store_exam(_sample_exam("grade003"))  # Q1 correct_answer is "А"

    forged = NVOExamSubmitRequest(
        exam_id="grade003",
        answers={"1": "Б"},  # actually wrong
        open_answer_images=[],
        questions=[_mcq(1, "Б")],  # attacker claims "Б" is correct — must be ignored
    )
    result = asyncio.run(submit_nvo_exam(forged, current_user=user, db=db))

    assert result.mcq_score == 0  # graded against the server's "А", not the forged "Б"


def test_submit_combines_mcq_and_open_into_one_percentage(db, make_user, monkeypatch):
    _fake_ai_grade(monkeypatch, is_correct=True)  # the one open question is correct
    user = make_user()
    _store_exam(_sample_exam("grade004"))

    result = _submit("grade004", {"1": "А", "2": "wrong", "3": "answer three"}, user, db)

    assert result.mcq_score == 1
    assert result.mcq_max_score == 2
    assert result.total_open_score == 1
    assert result.total_open_max_score == 1
    assert result.total_score == 2
    assert result.total_max_score == 3
    assert result.percentage_correct == round(2 / 3 * 100)


def test_submit_persists_an_nvo_attempt_row(db, make_user, monkeypatch):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("grade005", difficulty="hard", format="short"))

    _submit("grade005", {"1": "А", "2": "В", "3": "x"}, user, db)

    attempt = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == user.id, NvoAttempt.exam_id == "grade005")
        .one()
    )
    assert attempt.mcq_score == 2
    assert attempt.percentage_correct == 100
    assert attempt.difficulty == "hard"
    assert attempt.format == "short"
    assert attempt.xp_awarded is False


def test_resubmitting_the_same_exam_updates_the_same_row_not_a_duplicate(db, make_user, monkeypatch):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("grade006"))

    _submit("grade006", {"1": "А", "2": "wrong", "3": "x"}, user, db)
    _submit("grade006", {"1": "А", "2": "В", "3": "x"}, user, db)  # second attempt, now both right

    rows = db.query(NvoAttempt).filter(NvoAttempt.exam_id == "grade006").all()
    assert len(rows) == 1
    assert rows[0].mcq_score == 2  # reflects the latest submission


# ─── /nvo/award-xp: idempotent, server-derived ───────────────────────────────

def test_award_xp_refuses_without_a_prior_submission(db, make_user):
    user = make_user()
    request = NVOAwardXpRequest(exam_id="never-submitted", minutes_taken=10)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))
    assert exc.value.status_code == 400


def test_award_xp_uses_the_stored_percentage_and_difficulty(db, make_user, monkeypatch):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("award001", difficulty="hard"))
    _submit("award001", {"1": "А", "2": "В", "3": "x"}, user, db)  # 100%, hard

    request = NVOAwardXpRequest(exam_id="award001", minutes_taken=30)
    result = asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))

    assert result["percentage_correct"] == 100
    assert result["difficulty"] == "hard"
    assert result["difficulty_multiplier"] == 2.0


def test_award_xp_is_idempotent_per_attempt(db, make_user, monkeypatch):
    """Calling award-xp twice for the same exam must not grant XP twice — this
    is the exact exploit the old client-trusted endpoint was vulnerable to.
    """
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("award002", difficulty="hard"))
    _submit("award002", {"1": "А", "2": "В", "3": "x"}, user, db)

    request = NVOAwardXpRequest(exam_id="award002", minutes_taken=30)
    first = asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))
    second = asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))
    third = asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))

    assert second == first
    assert third == first
    assert second["xp_after"] == first["xp_after"]  # not accumulating further


def test_award_xp_clamps_minutes_taken_to_the_exam_format_duration(db, make_user, monkeypatch):
    """A short exam runs 30 minutes. Claiming 9999 minutes used to buy the
    -10% time penalty tier regardless of format; it must clamp to the
    format's own duration instead, landing in the fast (+40%) tier here.
    """
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_sample_exam("award003", format="short"))
    _submit("award003", {"1": "А", "2": "В", "3": "x"}, user, db)

    request = NVOAwardXpRequest(exam_id="award003", minutes_taken=9999)
    result = asyncio.run(award_nvo_exam_xp(request, current_user=user, db=db))

    assert result["minutes_taken"] <= 30
    assert result["time_multiplier"] == pytest.approx(1.4)
