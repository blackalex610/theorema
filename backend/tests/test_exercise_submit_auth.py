"""Regression tests for the /exercises/{id}/submit auth ordering.

The endpoint resolves the caller with `get_optional_user`, so an anonymous
request used to reach `_ai_equivalence_check` — an OpenAI call carrying
attacker-supplied answer text — and only got its 401 afterwards. Auth must be
resolved *before* any spend happens.
"""
import asyncio

import pytest
from fastapi import HTTPException

from app.models.curriculum import (
    Exercise as ExerciseModel,
    Grade as GradeModel,
    Lesson as LessonModel,
    Topic as TopicModel,
)
from app.routers import exercises as exercises_router
from app.schemas.curriculum import ExerciseAttemptCreate


@pytest.fixture
def exercise(db):
    """An exercise plus the grade/topic/lesson chain its FKs require."""
    grade = GradeModel(grade_number=99)  # out of the real 5-7 range, avoids collisions
    db.add(grade)
    db.commit()
    db.refresh(grade)

    topic = TopicModel(grade_id=grade.id, title="Test Topic")
    db.add(topic)
    db.commit()
    db.refresh(topic)

    lesson = LessonModel(topic_id=topic.id, title="Test Lesson")
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    ex = ExerciseModel(lesson_id=lesson.id, question="2 + 2 = ?", answer="4", solution="4")
    db.add(ex)
    db.commit()
    db.refresh(ex)

    yield ex

    db.delete(ex)
    db.delete(lesson)
    db.delete(topic)
    db.delete(grade)
    db.commit()


@pytest.fixture
def exploding_openai(monkeypatch):
    """Any OpenAI call during the test is a failure, not a mock result."""
    def _boom(**kwargs):
        raise AssertionError("_ai_equivalence_check reached without an authenticated user")

    monkeypatch.setattr(exercises_router, "_ai_equivalence_check", _boom)


def _submit(exercise_id, answer, current_user, db):
    return asyncio.run(exercises_router.submit_exercise(
        exercise_id=exercise_id,
        submission=ExerciseAttemptCreate(answer=answer),
        user_id=None,
        current_user=current_user,
        db=db,
    ))


def test_anonymous_submit_is_401_without_spending_openai(exercise, exploding_openai, db):
    """A wrong answer from an anonymous caller must 401, not hit OpenAI first."""
    with pytest.raises(HTTPException) as exc:
        _submit(exercise.id, "definitely-wrong", None, db)
    assert exc.value.status_code == 401


def test_anonymous_submit_cannot_pass_a_user_id(exercise, exploding_openai, db, make_user):
    """Passing ?user_id= must not stand in for a token."""
    victim = make_user()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(exercises_router.submit_exercise(
            exercise_id=exercise.id,
            submission=ExerciseAttemptCreate(answer="wrong"),
            user_id=victim.id,
            current_user=None,
            db=db,
        ))
    assert exc.value.status_code == 401


def test_authenticated_submit_still_grades(exercise, exploding_openai, db, make_user):
    """A correct answer resolves locally, so the happy path needs no OpenAI."""
    user = make_user()
    result = _submit(exercise.id, "4", user, db)
    assert result.correct is True
