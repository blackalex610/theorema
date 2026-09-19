"""Cross-device NVO attempt history: GET /nvo/attempts.

/nvo/submit has written an NvoAttempt row per graded sitting for a while, but
nothing could ever read those rows back — the exam page built its history list
purely from localStorage, so a student who switched devices or cleared browser
data lost every past score. The row was already the server's own scoring
record; this endpoint just makes it readable by the student it belongs to.

Scope note: an attempt summary carries scores and metadata, not the questions.
Generated exams live in nvo_exam_store under a 24h TTL, so a durable
per-question review would mean permanently storing every exam — a separate
decision. The history list is the cross-device part; review stays local.
"""
import asyncio
from datetime import datetime, timedelta

import pytest

from app.models.nvo_exam import NvoAttempt
from app.routers.nvo import list_nvo_attempts


@pytest.fixture(autouse=True)
def _clean_attempts(db):
    """Drop every attempt row around each test.

    nvo_attempts.user_id is a plain integer, not a cascading FK, so the
    make_user fixture deleting its users leaves attempts behind. SQLite then
    reuses those ids for the next test's user and the (user_id, exam_id)
    unique constraint fires on a fresh, unrelated row.
    """
    db.query(NvoAttempt).delete()
    db.commit()
    yield
    db.rollback()
    db.query(NvoAttempt).delete()
    db.commit()


def _attempt(db, user_id: int, exam_id: str, **overrides) -> NvoAttempt:
    defaults = dict(
        user_id=user_id,
        exam_id=exam_id,
        difficulty="standard",
        format="full",
        mcq_score=10,
        mcq_max_score=18,
        open_score=4,
        open_max_score=5,
        percentage_correct=61,
        xp_awarded=False,
        created_at=datetime.utcnow(),
        graded_at=datetime.utcnow(),
    )
    defaults.update(overrides)
    row = NvoAttempt(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _list(user, db, **kwargs):
    return asyncio.run(list_nvo_attempts(current_user=user, db=db, **kwargs))


def test_returns_nothing_when_the_student_has_never_sat_an_exam(make_user, db):
    assert _list(make_user(), db) == []


def test_returns_the_students_own_attempt(make_user, db):
    user = make_user()
    _attempt(db, user.id, "exam-1")

    (entry,) = _list(user, db)

    assert entry.exam_id == "exam-1"
    assert entry.percentage_correct == 61
    assert entry.difficulty == "standard"
    assert entry.format == "full"


def test_reports_combined_and_per_section_scores(make_user, db):
    user = make_user()
    _attempt(db, user.id, "exam-1", mcq_score=10, mcq_max_score=18,
             open_score=4, open_max_score=5)

    (entry,) = _list(user, db)

    assert (entry.mcq_score, entry.mcq_max_score) == (10, 18)
    assert (entry.open_score, entry.open_max_score) == (4, 5)
    # The history list shows one headline number; the server does that sum so
    # every client agrees on it.
    assert entry.score == 14
    assert entry.max_score == 23


def test_never_leaks_another_students_attempts(make_user, db):
    mine, theirs = make_user(), make_user()
    _attempt(db, mine.id, "mine")
    _attempt(db, theirs.id, "theirs")

    assert [e.exam_id for e in _list(mine, db)] == ["mine"]
    assert [e.exam_id for e in _list(theirs, db)] == ["theirs"]


def test_orders_newest_first(make_user, db):
    user = make_user()
    now = datetime.utcnow()
    _attempt(db, user.id, "older", graded_at=now - timedelta(days=2))
    _attempt(db, user.id, "newest", graded_at=now)
    _attempt(db, user.id, "middle", graded_at=now - timedelta(days=1))

    assert [e.exam_id for e in _list(user, db)] == ["newest", "middle", "older"]


def test_caps_the_list_so_a_heavy_user_cannot_return_everything(make_user, db):
    user = make_user()
    now = datetime.utcnow()
    for i in range(30):
        _attempt(db, user.id, f"exam-{i}", graded_at=now - timedelta(minutes=i))

    assert len(_list(user, db)) == 20               # default cap
    assert len(_list(user, db, limit=5)) == 5       # caller may ask for fewer


def test_clamps_an_out_of_range_limit(make_user, db):
    user = make_user()
    now = datetime.utcnow()
    for i in range(30):
        _attempt(db, user.id, f"exam-{i}", graded_at=now - timedelta(minutes=i))

    assert len(_list(user, db, limit=0)) == 1       # never an empty page
    assert len(_list(user, db, limit=9999)) == 30   # never unbounded


def test_reports_whether_xp_was_already_awarded(make_user, db):
    """The client greys out the XP panel for an attempt already paid out."""
    user = make_user()
    _attempt(db, user.id, "paid", xp_awarded=True, graded_at=datetime.utcnow())
    _attempt(db, user.id, "unpaid", xp_awarded=False,
             graded_at=datetime.utcnow() - timedelta(minutes=1))

    paid, unpaid = _list(user, db)
    assert paid.xp_awarded is True
    assert unpaid.xp_awarded is False


def test_handles_a_zero_max_score_without_dividing_by_zero(make_user, db):
    user = make_user()
    _attempt(db, user.id, "empty", mcq_score=0, mcq_max_score=0,
             open_score=0, open_max_score=0, percentage_correct=0)

    (entry,) = _list(user, db)
    assert entry.score == 0 and entry.max_score == 0
