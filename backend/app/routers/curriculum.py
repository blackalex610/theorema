import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session
from typing import List, Optional
from typing import cast
from openai import APIError
from app.database import get_db
import json
from app.models.curriculum import Grade as GradeModel, Topic as TopicModel, Lesson as LessonModel, Exercise as ExerciseModel, GeneratedLessonContent as GeneratedLessonContentModel
from app.schemas.curriculum import Grade, GradeWithTopics, Topic, TopicWithLessons, Lesson, LessonWithExercises, ExercisePublic, GeneratedTheoryResponse, VideoSearchQueriesResponse, GeneratedExamplesResponse, GeneratedExampleItem, DifficultyLevel as SchemaDifficultyLevel, ExerciseType as SchemaExerciseType
from app.models.progress import LessonProgress, UserProgress
from app.auth.dependencies import (
    enforce_ai_examples_generation,
    enforce_ai_exercise_generation,
    enforce_ai_theory_generation,
    get_current_user,
    require_admin,
    update_last_theory_at,
)
from app.models.user import User
from app.models.curriculum import ExerciseAttempt as ExerciseAttemptModel
from app.services.ai_theory_service import (
    generate_theory_content,
    generate_theory_from_standard,
    generate_video_search_queries,
    generate_example_problems,
    generate_exercises,
    AIQuotaExceededError,
    AIConfigurationError,
    AIServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])


def _normalize_difficulty(value: str | None) -> SchemaDifficultyLevel:
    normalized = (value or "").strip().lower()
    if normalized == "easy":
        return SchemaDifficultyLevel.EASY
    if normalized == "hard":
        return SchemaDifficultyLevel.HARD
    return SchemaDifficultyLevel.MEDIUM


def _normalize_exercise_type(value: str | None) -> SchemaExerciseType:
    normalized = (value or "").strip().lower()
    if normalized == "multiple_choice":
        return SchemaExerciseType.MULTIPLE_CHOICE
    if normalized == "algebra":
        return SchemaExerciseType.ALGEBRA
    # Legacy seed data sometimes used "text". Treat it as numeric input.
    return SchemaExerciseType.NUMERIC


def _load_exercises_public_for_lesson(db: Session, lesson_id: int) -> list[ExercisePublic]:
    rows = db.execute(
        sa_text(
            """
            SELECT id, lesson_id, question, difficulty, exercise_type
            FROM exercises
            WHERE lesson_id = :lesson_id
            ORDER BY id
            """
        ),
        {"lesson_id": lesson_id},
    ).mappings().all()

    return [
        ExercisePublic(
            id=cast(int, row["id"]),
            lesson_id=cast(int, row["lesson_id"]),
            question=cast(str, row["question"]),
            difficulty=_normalize_difficulty(cast(str | None, row["difficulty"])),
            exercise_type=_normalize_exercise_type(cast(str | None, row["exercise_type"])),
        )
        for row in rows
    ]


def _fallback_generated_examples(lesson_title: str) -> list[GeneratedExampleItem]:
    return [
        GeneratedExampleItem(
            difficulty="easy",
            problem=f"По темата \"{lesson_title}\": Реши 24 + 18.",
            solution="24 + 18 = 42.",
        ),
        GeneratedExampleItem(
            difficulty="easy",
            problem=f"По темата \"{lesson_title}\": Намери 56 - 29.",
            solution="56 - 29 = 27.",
        ),
        GeneratedExampleItem(
            difficulty="medium",
            problem=f"По темата \"{lesson_title}\": Изчисли 7 * 8 - 15.",
            solution="7 * 8 = 56, после 56 - 15 = 41.",
        ),
        GeneratedExampleItem(
            difficulty="hard",
            problem=f"По темата \"{lesson_title}\": Ако x + 17 = 45, намери x и провери резултата.",
            solution="x = 45 - 17 = 28. Проверка: 28 + 17 = 45.",
        ),
    ]


def _fallback_generated_theory(
    *,
    lesson_title: str,
    topic_title: str,
    grade_number: int,
    detail_level: str,
) -> str:
    detail_hint = {
        "concise": "Кратко обяснение с най-важните стъпки:",
        "standard": "Стандартно обяснение с ключови правила и пример:",
        "detailed": "Подробно обяснение с повече насоки и чести грешки:",
    }.get(detail_level, "Обяснение:")

    return (
        f"# {lesson_title}\n\n"
        f"**Клас:** {grade_number}. клас  \n"
        f"**Тема:** {topic_title}\n\n"
        f"{detail_hint}\n\n"
        "1. Определи какво се търси в задачата и кои данни са дадени.\n"
        "2. Избери подходящо правило/формула от урока.\n"
        "3. Замести внимателно стойностите и пресметни стъпка по стъпка.\n"
        "4. Провери отговора: разумен ли е резултатът и в правилните единици ли е.\n\n"
        "## Пример\n"
        f"По тема **{lesson_title}** реши проста задача по същия модел: "
        "запиши данните, приложи правилото и направи проверка накрая.\n\n"
        "## Чести грешки\n"
        "- Пропускане на знак при пресмятане.\n"
        "- Смесване на формули от различни уроци.\n"
        "- Прескачане на проверката на крайния резултат.\n"
    )


def _fallback_ai_exercises(*, lesson_title: str) -> list[dict]:
    return [
        {
            "question": f"По темата '{lesson_title}' пресметни: 36 + 27 = ?",
            "answer": "63",
            "solution": "36 + 27 = 63.",
            "difficulty": "easy",
            "exercise_type": "numeric",
        },
        {
            "question": f"По темата '{lesson_title}' пресметни: 84 - 39 = ?",
            "answer": "45",
            "solution": "84 - 39 = 45.",
            "difficulty": "easy",
            "exercise_type": "numeric",
        },
        {
            "question": f"По темата '{lesson_title}' реши: 7 * 8 - 12 = ?",
            "answer": "44",
            "solution": "7 * 8 = 56, 56 - 12 = 44.",
            "difficulty": "medium",
            "exercise_type": "numeric",
        },
        {
            "question": f"По темата '{lesson_title}' намери x, ако x + 18 = 52.",
            "answer": "34",
            "solution": "x = 52 - 18 = 34.",
            "difficulty": "medium",
            "exercise_type": "numeric",
        },
        {
            "question": f"По темата '{lesson_title}' пресметни: (45 / 5) + 17 = ?",
            "answer": "26",
            "solution": "45 / 5 = 9, 9 + 17 = 26.",
            "difficulty": "hard",
            "exercise_type": "numeric",
        },
    ]


def _store_generated_content(
    *,
    db: Session,
    lesson_id: int,
    detail_level: str,
    content: str,
) -> None:
    db.add(GeneratedLessonContentModel(
        lesson_id=lesson_id,
        detail_level=detail_level,
        content=content,
    ))
    try:
        db.commit()
    except IntegrityError:
        # Benign: another request cached the same (lesson_id, detail_level)
        # first. Roll back so the session stays usable and keep their row.
        db.rollback()
    except SQLAlchemyError:
        # Anything else is a real storage failure. Don't fail the request the
        # caller already paid an AI generation for, but never swallow it
        # silently — a permanently unwritable cache means unbounded AI spend.
        db.rollback()
        logger.exception(
            "Failed to cache generated content lesson_id=%s detail_level=%s",
            lesson_id, detail_level,
        )


@router.get("/grades", response_model=List[Grade])
async def get_grades(db: Session = Depends(get_db)):
    """
    Get all available grades (5, 6, 7)
    """
    grades = db.query(GradeModel).order_by(GradeModel.grade_number).all()
    return grades


@router.get("/grades/{grade_id}", response_model=GradeWithTopics)
async def get_grade(grade_id: int, db: Session = Depends(get_db)):
    """
    Get a specific grade with its topics
    """
    grade = db.query(GradeModel).filter(GradeModel.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    return grade


@router.get("/grades/{grade_id}/topics", response_model=List[Topic])
async def get_topics_by_grade(grade_id: int, db: Session = Depends(get_db)):
    """
    Get all topics for a specific grade
    """
    # Verify grade exists
    grade =db.query(GradeModel).filter(GradeModel.id == grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    
    topics = db.query(TopicModel).filter(TopicModel.grade_id == grade_id).all()
    return topics


@router.get("/topics/{topic_id}", response_model=TopicWithLessons)
async def get_topic(topic_id: int, db: Session = Depends(get_db)):
    """
    Get a specific topic with its lessons
    """
    topic = db.query(TopicModel).filter(TopicModel.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


@router.get("/topics/{topic_id}/lessons", response_model=List[Lesson])
async def get_lessons_by_topic(topic_id: int, db: Session = Depends(get_db)):
    """
    Get all lessons for a specific topic
    """
    # Verify topic exists
    topic = db.query(TopicModel).filter(TopicModel.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    lessons = db.query(LessonModel).filter(LessonModel.topic_id == topic_id).all()
    return lessons


@router.get("/lessons/{lesson_id}", response_model=LessonWithExercises)
async def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """
    Get a specific lesson with its exercises
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    exercises = _load_exercises_public_for_lesson(db, lesson_id)
    return LessonWithExercises(
        id=cast(int, lesson.id),
        topic_id=cast(int, lesson.topic_id),
        title=cast(str, lesson.title),
        content=cast(str | None, lesson.content),
        exercises=exercises,
    )


@router.get("/lessons/{lesson_id}/exercises", response_model=List[ExercisePublic])
async def get_exercises_by_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """
    Get all exercises for a specific lesson (without answers)
    """
    # Verify lesson exists
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    
    return _load_exercises_public_for_lesson(db, lesson_id)


@router.get("/lessons/{lesson_id}/content-status")
async def get_content_status(lesson_id: int, db: Session = Depends(get_db)):
    """Return which detail levels (theory + examples) are already cached in the DB."""
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    cached = db.query(GeneratedLessonContentModel).filter(
        GeneratedLessonContentModel.lesson_id == lesson_id
    ).all()

    cached_levels = [row.detail_level for row in cached]
    return {"lesson_id": lesson_id, "cached_levels": cached_levels}


@router.get("/lessons/{lesson_id}/generated-theory", response_model=GeneratedTheoryResponse)
async def get_generated_theory(
    lesson_id: int,
    detail_level: str = Query(default="standard", pattern="^(concise|standard|detailed)$"),
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Return cached theory if available; otherwise generate, store, and return.

    detail_level: "concise" | "standard" (default) | "detailed"
    When generating concise/detailed, uses cached standard as base if available.

    Uncached generations require authentication and count against the daily ai_theory limit.
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Check cache first — no rate limit for cached content
    cached = db.query(GeneratedLessonContentModel).filter(
        GeneratedLessonContentModel.lesson_id == lesson_id,
        GeneratedLessonContentModel.detail_level == detail_level,
    ).first()
    if cached:
        return GeneratedTheoryResponse(
            lesson_id=cast(int, lesson.id),
            title=cast(str, lesson.title),
            content=cast(str, cached.content),
        )

    theory_user = enforce_ai_theory_generation(authorization=authorization, db=db)

    topic = db.query(TopicModel).filter(TopicModel.id == lesson.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    grade = db.query(GradeModel).filter(GradeModel.id == topic.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    lesson_title = cast(str, lesson.title)
    topic_title = cast(str, topic.title)
    grade_number = cast(int, grade.grade_number)

    try:
        # If generating concise/detailed and standard already cached, use it as base
        if detail_level in ("concise", "detailed"):
            standard_cached = db.query(GeneratedLessonContentModel).filter(
                GeneratedLessonContentModel.lesson_id == lesson_id,
                GeneratedLessonContentModel.detail_level == "standard",
            ).first()
            if standard_cached:
                content = generate_theory_from_standard(
                    standard_content=cast(str, standard_cached.content),
                    lesson_title=lesson_title,
                    detail_level=detail_level,
                )
            else:
                content = generate_theory_content(
                    lesson_title=lesson_title,
                    topic_title=topic_title,
                    grade_number=grade_number,
                    detail_level=detail_level,
                )
        else:
            content = generate_theory_content(
                lesson_title=lesson_title,
                topic_title=topic_title,
                grade_number=grade_number,
                detail_level=detail_level,
            )
    except (AIQuotaExceededError, AIConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _store_generated_content(
        db=db,
        lesson_id=lesson_id,
        detail_level=detail_level,
        content=content,
    )
    update_last_theory_at(theory_user, db)

    return GeneratedTheoryResponse(
        lesson_id=cast(int, lesson.id),
        title=cast(str, lesson.title),
        content=content,
    )


@router.get("/lessons/{lesson_id}/video-search-queries", response_model=VideoSearchQueriesResponse)
async def get_video_search_queries(
    lesson_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get AI-rephrased queries for YouTube search fallback.

    SECURITY: this hits OpenAI on *every* call with no cache of any kind, so
    anonymous access meant unbounded spend against our key. No daily credit is
    charged — it is an incidental helper fired on lesson open, and 429-ing it
    would break the page for a user who legitimately spent their theory quota.
    Burst abuse is bounded by the per-IP limiter on /curriculum/lessons/.
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    topic = db.query(TopicModel).filter(TopicModel.id == lesson.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    grade = db.query(GradeModel).filter(GradeModel.id == topic.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    lesson_title = cast(str, lesson.title)
    topic_title = cast(str, topic.title)
    grade_number = cast(int, grade.grade_number)

    try:
        queries = generate_video_search_queries(
            lesson_title=lesson_title,
            topic_title=topic_title,
            grade_number=grade_number,
        )
    except Exception:
        # Safe fallback without failing the user flow.
        queries = [
            f"{lesson_title} математика",
            f"{topic_title} {grade_number} клас",
            f"{lesson_title} обяснение",
            f"{lesson_title} задачи",
            f"{lesson_title} матура",
        ]

    if not queries:
        queries = [f"{lesson_title} математика"]

    return VideoSearchQueriesResponse(
        lesson_id=cast(int, lesson.id),
        queries=queries,
    )


@router.get("/lessons/{lesson_id}/generated-examples", response_model=GeneratedExamplesResponse)
async def get_generated_examples(
    lesson_id: int,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Return cached examples if available; otherwise generate, store, and return.

    Cached examples are served to anyone. An uncached generation requires
    authentication and costs one ai_theory credit — previously it was an
    unauthenticated, unmetered OpenAI call.
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    # Check cache first
    cached = db.query(GeneratedLessonContentModel).filter(
        GeneratedLessonContentModel.lesson_id == lesson_id,
        GeneratedLessonContentModel.detail_level == "examples",
    ).first()
    if cached:
        try:
            examples_data = json.loads(cast(str, cached.content))
            return GeneratedExamplesResponse(
                lesson_id=cast(int, lesson.id),
                title=cast(str, lesson.title),
                examples=[GeneratedExampleItem(**e) for e in examples_data],
            )
        except Exception:
            # Corrupt cache row: evict it, otherwise every future request pays
            # for a fresh AI generation while the bad row sits there forever.
            logger.warning(
                "Evicting corrupt generated-content cache row id=%s lesson_id=%s level=examples",
                cached.id, lesson_id,
            )
            db.delete(cached)
            db.commit()

    enforce_ai_examples_generation(authorization=authorization, db=db)

    topic = db.query(TopicModel).filter(TopicModel.id == lesson.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    grade = db.query(GradeModel).filter(GradeModel.id == topic.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    lesson_title = cast(str, lesson.title)
    topic_title = cast(str, topic.title)
    grade_number = cast(int, grade.grade_number)

    try:
        examples = generate_example_problems(
            lesson_title=lesson_title,
            topic_title=topic_title,
            grade_number=grade_number,
        )
    except (AIQuotaExceededError, AIConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not examples:
        raise HTTPException(status_code=502, detail="AI returned no examples")

    example_items = [
        GeneratedExampleItem(
            difficulty=e.get("difficulty", "medium"),
            problem=e["problem"],
            solution=e["solution"],
        )
        for e in examples
    ]

    _store_generated_content(
        db=db,
        lesson_id=lesson_id,
        detail_level="examples",
        content=json.dumps([{"difficulty": e.difficulty, "problem": e.problem, "solution": e.solution} for e in example_items], ensure_ascii=False),
    )

    return GeneratedExamplesResponse(
        lesson_id=cast(int, lesson.id),
        title=lesson_title,
        examples=example_items,
    )


@router.get("/lessons/{lesson_id}/ai-exercises", response_model=List[ExercisePublic])
async def get_ai_exercises(
    lesson_id: int,
    regenerate: bool = False,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """Return cached AI-generated exercises for a lesson; generate & save them if none exist.

    Cached exercises are served without auth. New AI generation requires login and
    counts against the daily ai_exercises limit.
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    existing = _load_exercises_public_for_lesson(db, lesson_id)
    if existing and not regenerate:
        return existing

    enforce_ai_exercise_generation(authorization=authorization, db=db)

    # Delete old exercises (and their attempts) then generate fresh ones
    if existing:
        db.execute(
            sa_text(
                """
                DELETE FROM exercise_attempts
                WHERE exercise_id IN (
                    SELECT id FROM exercises WHERE lesson_id = :lesson_id
                )
                """
            ),
            {"lesson_id": lesson_id},
        )
        db.execute(
            sa_text("DELETE FROM exercises WHERE lesson_id = :lesson_id"),
            {"lesson_id": lesson_id},
        )
        db.commit()

    topic = db.query(TopicModel).filter(TopicModel.id == lesson.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    grade = db.query(GradeModel).filter(GradeModel.id == topic.grade_id).first()
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    try:
        raw_exercises = generate_exercises(
            lesson_title=cast(str, lesson.title),
            topic_title=cast(str, topic.title),
            grade_number=cast(int, grade.grade_number),
        )
    except (AIQuotaExceededError, AIConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not raw_exercises:
        raise HTTPException(status_code=500, detail="AI returned no exercises")

    new_exercises = []
    for e in raw_exercises:
        normalized_difficulty = _normalize_difficulty(cast(str | None, e.get("difficulty"))).value
        normalized_exercise_type = _normalize_exercise_type(cast(str | None, e.get("exercise_type"))).value
        obj = ExerciseModel(
            lesson_id=lesson_id,
            question=e["question"],
            answer=e["answer"],
            solution=e.get("solution", ""),
            difficulty=normalized_difficulty,
            exercise_type=normalized_exercise_type,
        )
        db.add(obj)
        new_exercises.append(obj)

    db.commit()
    return _load_exercises_public_for_lesson(db, lesson_id)


@router.delete("/lessons/{lesson_id}/exercises/reset", status_code=204)
async def reset_lesson_exercises(
    lesson_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete all exercises and progress for a lesson so AI can regenerate them.

    SECURITY: this used to have no auth dependency at all — any anonymous
    caller could destroy every user's exercise attempts and progress for a
    lesson with one unauthenticated request.
    """
    lesson = db.query(LessonModel).filter(LessonModel.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    exercise_ids = [
        row.id for row in
        db.query(ExerciseModel.id).filter(ExerciseModel.lesson_id == lesson_id).all()
    ]
    if exercise_ids:
        db.query(ExerciseAttemptModel).filter(
            ExerciseAttemptModel.exercise_id.in_(exercise_ids)
        ).delete(synchronize_session=False)
        db.query(ExerciseModel).filter(ExerciseModel.lesson_id == lesson_id).delete(synchronize_session=False)

    # Clear lesson-level progress
    db.query(LessonProgress).filter(LessonProgress.lesson_id == lesson_id).delete(synchronize_session=False)
    db.commit()
