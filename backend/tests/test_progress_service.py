"""Tests for the XP/level rules and for the batched progress queries.

The XP pipeline decides every number a student sees on the dashboard and had no
coverage at all. The query-count tests at the bottom pin the N+1 fix: the
per-topic and per-lesson lookups now happen once for the whole page, so the
cost must not grow with the size of the curriculum.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app.models.curriculum import Grade, Lesson, Topic
from app.models.progress import LessonProgress, UserProgress
from app.services.progress_service import (
    LEVEL_THRESHOLDS,
    ProgressService,
    _calculate_nvo_base_xp,
    _calculate_streak_multiplier,
    _calculate_time_bonus_multiplier,
    _generate_level_thresholds,
    _get_difficulty_multiplier,
    calculate_nvo_exam_xp,
)


# ─── Level curve ─────────────────────────────────────────────────────────────

def test_level_one_starts_at_zero_xp():
    assert LEVEL_THRESHOLDS[0] == 0


def test_the_level_curve_is_strictly_increasing():
    """A flat or backwards step would make a level unreachable or instant."""
    assert all(b > a for a, b in zip(LEVEL_THRESHOLDS, LEVEL_THRESHOLDS[1:]))


def test_the_level_curve_gets_steeper():
    """The curve is meant to slow down, not speed up, as levels go on."""
    increments = [b - a for a, b in zip(LEVEL_THRESHOLDS, LEVEL_THRESHOLDS[1:])]
    assert all(b >= a for a, b in zip(increments, increments[1:]))


def test_the_curve_covers_every_requested_level():
    assert len(_generate_level_thresholds(50)) == 51


# ─── Level lookup ────────────────────────────────────────────────────────────

@pytest.fixture
def service(db):
    return ProgressService(db)


def test_zero_xp_is_level_one(service):
    info = service._get_level_info(0)
    assert info["level"] == 1
    assert info["xp_into_level"] == 0


def test_landing_exactly_on_a_threshold_grants_the_level(service):
    for level in (2, 5, 10):
        info = service._get_level_info(LEVEL_THRESHOLDS[level - 1])
        assert info["level"] == level, f"{LEVEL_THRESHOLDS[level - 1]} XP should be level {level}"


def test_one_xp_short_of_a_threshold_does_not_grant_the_level(service):
    info = service._get_level_info(LEVEL_THRESHOLDS[4] - 1)
    assert info["level"] == 4


@pytest.mark.parametrize("total_xp", [0, 1, 500, 5_000, 250_000, 10_000_000])
def test_level_progress_stays_in_range(service, total_xp):
    info = service._get_level_info(total_xp)
    assert 0 <= info["progress_percentage"] <= 100
    assert info["xp_to_next_level"] >= 0
    assert info["level"] >= 1


# ─── Streak multiplier ───────────────────────────────────────────────────────

@pytest.mark.parametrize("streak,expected", [
    (0, 1.0),
    (1, 1.0),
    (2, 1.0),
    (3, 1.1),    # first tier boundary
    (6, 1.1),
    (7, 1.25),   # second tier boundary
    (13, 1.25),
    (14, 1.5),   # top tier boundary
    (365, 1.5),  # and it stops there
])
def test_streak_multiplier_boundaries(streak, expected):
    assert _calculate_streak_multiplier(streak) == pytest.approx(expected)


# ─── NVO base XP ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("percentage,expected", [
    (0, 10),     # bottom of the fail tier
    (49, 25),    # top of the fail tier
    (50, 30),    # low pass starts
    (69, 60),
    (70, 70),    # good pass starts
    (84, 120),
    (85, 130),   # excellent starts
    (94, 200),
    (95, 220),   # perfect tier starts
    (100, 300),  # and tops out
])
def test_nvo_base_xp_tier_boundaries(percentage, expected):
    assert _calculate_nvo_base_xp(percentage) == expected


def test_nvo_base_xp_never_decreases_with_a_better_score():
    """A student who answered more questions right must never earn less."""
    values = [_calculate_nvo_base_xp(p) for p in range(0, 101)]
    assert all(b >= a for a, b in zip(values, values[1:]))


# ─── Difficulty and time multipliers ─────────────────────────────────────────

@pytest.mark.parametrize("difficulty,expected", [
    ("easy", 0.5),
    ("standard", 1.0),
    ("hard", 2.0),
    ("HARD", 2.0),          # case-insensitive
    ("nonsense", 1.0),      # unknown falls back to standard, never 0
])
def test_difficulty_multiplier(difficulty, expected):
    assert _get_difficulty_multiplier(difficulty) == pytest.approx(expected)


@pytest.mark.parametrize("minutes,expected", [
    (0, 1.40),
    (60, 1.40),   # last minute of the fast band
    (61, 1.20),
    (75, 1.20),
    (76, 1.00),
    (90, 1.00),
    (91, 0.90),
    (600, 0.90),  # the penalty is capped
])
def test_time_bonus_boundaries(minutes, expected):
    assert _calculate_time_bonus_multiplier(minutes) == pytest.approx(expected)


# ─── The full pipeline ───────────────────────────────────────────────────────

def test_the_pipeline_applies_difficulty_then_time():
    """Order matters: time is applied to the difficulty-adjusted total."""
    result = calculate_nvo_exam_xp(percentage_correct=100, difficulty="hard", minutes_taken=30)

    assert result["base_xp"] == 300
    assert result["difficulty_multiplier"] == 2.0
    assert result["time_multiplier"] == pytest.approx(1.4)
    assert result["final_xp"] == int(int(300 * 2.0) * 1.4)


def test_the_breakdown_adds_up_to_the_final_xp():
    """The UI shows the components; they must reconcile with the total."""
    result = calculate_nvo_exam_xp(percentage_correct=72, difficulty="standard", minutes_taken=80)

    assert (
        result["base_xp"] + result["difficulty_bonus_xp"] + result["time_bonus_xp"]
        == result["final_xp"]
    )


@pytest.mark.parametrize("percentage,difficulty,minutes", [
    (0, "easy", 600),
    (0, "easy", 0),
    (100, "hard", 0),
    (13, "nonsense", 91),
])
def test_awarded_xp_is_never_negative(percentage, difficulty, minutes):
    assert calculate_nvo_exam_xp(percentage, difficulty, minutes)["final_xp"] >= 0


def test_a_slow_run_is_worth_less_than_a_fast_one():
    fast = calculate_nvo_exam_xp(90, "standard", 30)["final_xp"]
    slow = calculate_nvo_exam_xp(90, "standard", 120)["final_xp"]
    assert slow < fast


# ─── Query counting: the N+1 regression guard ────────────────────────────────

@contextmanager
def counting_queries(session):
    """Count SQL statements issued on the session's connection."""
    counter = {"n": 0}
    bind = session.get_bind()

    def _on_execute(conn, cursor, statement, parameters, context, executemany):
        counter["n"] += 1

    event.listen(bind, "before_cursor_execute", _on_execute)
    try:
        yield counter
    finally:
        event.remove(bind, "before_cursor_execute", _on_execute)


@pytest.fixture
def curriculum(db):
    """Build a curriculum of a given size, with progress rows already present.

    Pre-creating the progress rows keeps the test on the read path; the cold
    path deliberately still writes one row per missing topic.
    """
    created: list = []

    def _build(user_id: int, topic_count: int, lessons_per_topic: int = 2):
        grade = Grade(grade_number=5 + len(created))
        db.add(grade)
        db.flush()
        created.append(grade)

        for t in range(topic_count):
            topic = Topic(grade_id=grade.id, title=f"Тема {t}", description="d")
            db.add(topic)
            db.flush()
            db.add(UserProgress(
                user_id=user_id,
                topic_id=topic.id,
                completed_exercises=2,
                total_exercises=4,
                accuracy_percentage=50.0,
            ))
            for n in range(lessons_per_topic):
                lesson = Lesson(topic_id=topic.id, title=f"Урок {n}", content="c")
                db.add(lesson)
                db.flush()
                db.add(LessonProgress(
                    user_id=user_id,
                    lesson_id=lesson.id,
                    completed_exercises=1,
                    total_exercises=2,
                    completed=(n == 0),
                ))
        db.commit()
        return grade

    yield _build

    for grade in created:
        db.delete(grade)
    db.commit()
    db.query(UserProgress).delete()
    db.query(LessonProgress).delete()
    db.commit()


def test_topic_progress_cost_does_not_grow_with_the_curriculum(db, curriculum, service):
    """The whole point of the fix: 3 topics and 15 topics cost the same.

    Both measurements use the same user, who already has a progress row for
    every topic — otherwise the cold path (one write per missing row) would
    dominate the count and hide what is being measured.
    """
    curriculum(user_id=9001, topic_count=3)
    with counting_queries(db) as small:
        rows_small = service.get_topic_progress_list(9001)

    curriculum(user_id=9001, topic_count=12)
    with counting_queries(db) as large:
        rows_large = service.get_topic_progress_list(9001)

    assert len(rows_small) == 3
    assert len(rows_large) == 15  # both grades' topics are visible
    assert large["n"] == small["n"], (
        f"query count grew from {small['n']} to {large['n']} — the per-topic "
        "lookups are back"
    )


def test_topic_progress_still_reports_the_right_numbers(db, curriculum, service):
    curriculum(user_id=9003, topic_count=2, lessons_per_topic=3)

    rows = service.get_topic_progress_list(9003)

    assert len(rows) == 2
    for row in rows:
        assert row["total_lessons"] == 3
        assert row["lessons_completed"] == 1   # only the first lesson is completed
        assert row["grade_number"] >= 5        # resolved without re-fetching the topic
        assert row["completed_exercises"] == 2
        assert row["total_exercises"] == 4
        assert row["accuracy"] == pytest.approx(50.0)
        assert row["needs_practice"] is True   # accuracy < 60 with work done


def test_lesson_progress_cost_does_not_grow_with_the_topic(db, curriculum, service):
    grade_small = curriculum(user_id=9004, topic_count=1, lessons_per_topic=2)
    topic_small = db.query(Topic).filter(Topic.grade_id == grade_small.id).first()
    with counting_queries(db) as small:
        rows_small = service.get_lesson_progress_list(9004, int(topic_small.id))

    grade_large = curriculum(user_id=9005, topic_count=1, lessons_per_topic=10)
    topic_large = db.query(Topic).filter(Topic.grade_id == grade_large.id).first()
    with counting_queries(db) as large:
        rows_large = service.get_lesson_progress_list(9005, int(topic_large.id))

    assert len(rows_small) == 2
    assert len(rows_large) == 10
    assert large["n"] == small["n"], (
        f"query count grew from {small['n']} to {large['n']} — the per-lesson "
        "lookups are back"
    )


def test_lesson_progress_still_reports_the_right_numbers(db, curriculum, service):
    grade = curriculum(user_id=9006, topic_count=1, lessons_per_topic=3)
    topic = db.query(Topic).filter(Topic.grade_id == grade.id).first()

    rows = service.get_lesson_progress_list(9006, int(topic.id))

    assert [row["completed"] for row in rows] == [True, False, False]
    assert all(row["progress_percentage"] == pytest.approx(50.0) for row in rows)


def test_a_maxed_out_player_does_not_get_a_broken_progress_bar(service):
    """Past the last threshold there is no next level to be a fraction of.

    The placeholder "next level" sits 1000 XP above the top, so an uncapped
    ratio rendered as e.g. 911577% on the dashboard.
    """
    info = service._get_level_info(LEVEL_THRESHOLDS[-1] + 5_000_000)
    assert info["progress_percentage"] == 100.0
    assert info["level"] == len(LEVEL_THRESHOLDS)
