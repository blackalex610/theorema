"""Per-question results: the data every teacher and school view is built on.

/nvo/submit already graded each question individually and then kept only
three aggregate numbers, so "Мария scored 62%" was recoverable and "half the
class fails inequalities" was not — and could never be backfilled, because
the generated paper expires 24h after the sitting.

These tests pin that each graded question is persisted once, with the
canonical topic it belongs to, and that a re-submit re-grades rather than
accumulating duplicate rows.
"""
import asyncio

import pytest

from app.models.nvo_exam import NvoAttempt, NvoAttemptItem
from app.routers.nvo import (
    NVOExam,
    NVOExamSubmitRequest,
    NVOQuestion,
    _store_exam,
    submit_nvo_exam,
)


@pytest.fixture(autouse=True)
def _no_attempt_rows_leak(db):
    """Attempts and their items outlive the user rows that own them.

    The suite shares one SQLite file, `make_user` deletes its users on
    teardown, and SQLite then hands the same rowid to the next test's user —
    so without this, one test's items are indistinguishable from the next
    test's by user_id. (That reuse is a test artefact; the real orphaning
    risk is covered by test_user_data.py.)
    """
    def _clear():
        db.query(NvoAttemptItem).delete(synchronize_session=False)
        db.query(NvoAttempt).delete(synchronize_session=False)
        db.commit()

    # Before as well as after: other modules in the suite write attempts too,
    # and the whole run shares one SQLite file.
    _clear()
    yield
    _clear()


def _mcq(number: int, correct: str, topic: str) -> NVOQuestion:
    return NVOQuestion(
        number=number,
        question=f"MCQ {number}",
        topic=topic,
        difficulty="easy",
        diagram=False,
        options=["А) x", "Б) y", "В) z", "Г) w"],
        correct_answer=correct,
        kind="mc",
    )


def _open(number: int, correct: str, topic: str) -> NVOQuestion:
    return NVOQuestion(
        number=number,
        question=f"Open {number}",
        topic=topic,
        difficulty="hard",
        diagram=False,
        options=None,
        correct_answer=correct,
        kind="open",
    )


def _exam(exam_id: str) -> NVOExam:
    return NVOExam(
        exam_id=exam_id,
        questions=[
            _mcq(1, "А", "inequality_integer_bound"),
            _mcq(2, "В", "geometry_rhombus_or_circumcenter_diagram"),
            _open(3, "answer three", "open_geometry_proof_and_calculation_diagram"),
        ],
        difficulty="actual",
        format="full",
    )


def _fake_ai_grade(monkeypatch, *, is_correct: bool):
    import app.routers.nvo as nvo_module

    monkeypatch.setattr(
        nvo_module,
        "_ai_grade",
        lambda **kwargs: (is_correct, "extracted", "feedback"),
    )


def _submit(exam_id: str, answers: dict, user, db):
    payload = NVOExamSubmitRequest(exam_id=exam_id, answers=answers, open_answer_images=[])
    return asyncio.run(submit_nvo_exam(payload, current_user=user, db=db))


def _items(db, user_id: int) -> list[NvoAttemptItem]:
    return (
        db.query(NvoAttemptItem)
        .filter(NvoAttemptItem.user_id == user_id)
        .order_by(NvoAttemptItem.question_number)
        .all()
    )


def test_submit_persists_one_row_per_graded_question(monkeypatch, db, make_user):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_exam("items001"))

    _submit("items001", {"1": "А", "2": "Г", "3": "answer three"}, user, db)

    rows = _items(db, user.id)
    assert [r.question_number for r in rows] == [1, 2, 3]
    assert [r.is_correct for r in rows] == [True, False, True]


def test_each_item_carries_the_canonical_topic_not_the_raw_string(monkeypatch, db, make_user):
    """The two generators spell the same topic differently; diagnostics
    aggregate on the resolved key or they aggregate wrongly."""
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_exam("items002"))

    _submit("items002", {"1": "А", "2": "В", "3": "x"}, user, db)

    by_number = {r.question_number: r.topic_key for r in _items(db, user.id)}
    assert by_number[1] == "inequality"
    assert by_number[2] == "geom_quadrilateral"
    assert by_number[3] == "open_geometry_proof"


def test_items_record_the_question_kind(monkeypatch, db, make_user):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_exam("items003"))

    _submit("items003", {"1": "А", "2": "В", "3": "x"}, user, db)

    assert [r.kind for r in _items(db, user.id)] == ["mc", "mc", "open"]


def test_an_unrecognised_topic_is_recorded_as_other_not_guessed(monkeypatch, db, make_user):
    """The LLM path can emit any topic string it likes. Mislabelling it into
    a real topic would put wrong numbers on a teacher's screen."""
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    exam = NVOExam(
        exam_id="items004",
        questions=[_mcq(1, "А", "квадратни криволинейни нещица")],
        difficulty="actual",
        format="full",
    )
    _store_exam(exam)

    _submit("items004", {"1": "А"}, user, db)

    assert [r.topic_key for r in _items(db, user.id)] == ["other"]


def test_resubmitting_regrades_instead_of_duplicating_rows(monkeypatch, db, make_user):
    """A network retry must not double every question — the roster's
    percentages are computed off these rows."""
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_exam("items005"))

    _submit("items005", {"1": "Б", "2": "Б", "3": "x"}, user, db)
    first = _items(db, user.id)
    assert [r.is_correct for r in first] == [False, False, True]

    _submit("items005", {"1": "А", "2": "В", "3": "x"}, user, db)

    second = _items(db, user.id)
    assert len(second) == 3, "re-submit accumulated duplicate item rows"
    assert [r.is_correct for r in second] == [True, True, True]


def test_items_are_linked_to_their_attempt(monkeypatch, db, make_user):
    _fake_ai_grade(monkeypatch, is_correct=True)
    user = make_user()
    _store_exam(_exam("items006"))

    _submit("items006", {"1": "А", "2": "В", "3": "x"}, user, db)

    attempt = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == user.id, NvoAttempt.exam_id == "items006")
        .one()
    )
    assert {r.attempt_id for r in _items(db, user.id)} == {attempt.id}


def test_two_students_items_do_not_mix(monkeypatch, db, make_user):
    _fake_ai_grade(monkeypatch, is_correct=True)
    one = make_user()
    two = make_user()
    _store_exam(_exam("items007"))

    _submit("items007", {"1": "А", "2": "В", "3": "x"}, one, db)
    _submit("items007", {"1": "Б", "2": "Б", "3": "x"}, two, db)

    assert [r.is_correct for r in _items(db, one.id)] == [True, True, True]
    assert [r.is_correct for r in _items(db, two.id)] == [False, False, True]
