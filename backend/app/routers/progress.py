from datetime import date as dt_date
from random import Random
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, cast
from app.auth.dependencies import get_optional_user, require_admin
from app.database import get_db
from app.models.curriculum import DifficultyLevel, Exercise, Lesson, Topic
from app.models.progress import UserDailyMission, UserMissionExercise, UserXpProfile, XpEvent
from app.models.user import User
from app.schemas.progress import (
    DashboardStats,
    XpSummary,
    TopicProgressSummary,
    LessonProgressSummary,
    ProgressRecommendations,
    UserLimitInfo
)
from app.services.progress_service import ProgressService

router = APIRouter(prefix="/progress", tags=["Progress"])


def _resolve_user_id(current_user: Optional[User], user_id: Optional[int]) -> int:
    if current_user is not None:
        return int(cast(int, current_user.id))
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/xp-summary", response_model=XpSummary)
async def get_xp_summary(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Get the student's current XP snapshot and derived level thresholds."""
    service = ProgressService(db)
    resolved_user_id = _resolve_user_id(current_user, user_id)
    return service.get_xp_summary(resolved_user_id)


@router.post("/record-activity", response_model=XpSummary)
async def record_activity(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Record a daily login / activity event and update the streak counter."""
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    summary = service.update_streak(resolved_user_id)
    service.evaluate_and_grant_badges(resolved_user_id)
    return summary


@router.get("/badges")
async def get_badges(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Return all badges the user has earned."""
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    return service.get_user_badges(resolved_user_id)


@router.post("/badges/evaluate")
async def evaluate_badges(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Evaluate badge criteria and grant newly earned badges. Returns new badge keys."""
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    newly_granted = service.evaluate_and_grant_badges(resolved_user_id)
    all_badges = service.get_user_badges(resolved_user_id)
    return {"newly_granted": newly_granted, "badges": all_badges}


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get overall student statistics for the dashboard.
    
    Returns:
    - total_exercises_completed: Number of unique exercises solved correctly
    - total_exercises_attempted: Number of unique exercises attempted
    - accuracy_percentage: Overall accuracy across all attempts
    - topics_started: Number of topics with at least one attempt
    - topics_completed: Number of fully completed topics
    - lessons_started: Number of lessons with at least one attempt
    - lessons_completed: Number of fully completed lessons
    """
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    stats = service.get_dashboard_stats(resolved_user_id)
    return stats


@router.get("/topics", response_model=List[TopicProgressSummary])
async def get_topic_progress(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get progress for all topics.
    
    Returns list of topics with:
    - Progress percentage (completed exercises / total exercises)
    - Accuracy percentage
    - Lessons completed count
    - Flag indicating if topic needs practice (accuracy < 60%)
    """
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    progress_list = service.get_topic_progress_list(resolved_user_id)
    return progress_list


@router.get("/lessons/{topic_id}", response_model=List[LessonProgressSummary])
async def get_lesson_progress(
    topic_id: int,
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get progress for all lessons within a specific topic.
    
    Returns list of lessons with:
    - Progress percentage
    - Completed exercises count
    - Completion status
    """
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    progress_list = service.get_lesson_progress_list(resolved_user_id, topic_id)
    return progress_list


@router.get("/recommendations", response_model=ProgressRecommendations)
async def get_recommendations(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized learning recommendations.
    
    Returns:
    - weak_topics: Topics where student has accuracy < 60%
    - recommended_lessons: Specific lessons to practice in weak topics
    - encouragement_message: Motivational message based on progress
    
    This helps identify areas where the student needs more practice.
    """
    resolved_user_id = _resolve_user_id(current_user, user_id)
    service = ProgressService(db)
    recommendations = service.get_recommendations(resolved_user_id)
    return recommendations


def _difficulty_label(value: str) -> str:
    if value == "easy":
        return "Лесно"
    if value == "hard":
        return "Трудно"
    return "Средно"


def _seed_for_day(user_id: int, day: dt_date) -> int:
    raw = f"{user_id}:{day.isoformat()}".encode("utf-8")
    return int(hashlib.md5(raw).hexdigest(), 16)


def _find_lesson_for_topic_and_difficulty(db: Session, topic_id: int, difficulty: DifficultyLevel) -> int | None:
    row = (
        db.query(Lesson.id)
        .join(Exercise, Exercise.lesson_id == Lesson.id)
        .filter(Lesson.topic_id == topic_id, Exercise.difficulty == difficulty)
        .group_by(Lesson.id)
        .first()
    )
    return int(row[0]) if row else None


def _serialize_mission(m: UserDailyMission) -> dict:
    required_difficulty = str(cast(str | None, m.required_difficulty) or "medium")
    target_count = int(cast(int | None, m.target_count) or 0)
    correct_count = int(cast(int | None, m.correct_count) or 0)
    return {
        "id": str(cast(str | None, m.mission_key) or ""),
        "title": str(cast(str | None, m.title) or ""),
        "description": str(cast(str | None, m.description) or ""),
        "duration": "10 мин",
        "difficulty": _difficulty_label(required_difficulty),
        "xp_base": int(cast(int | None, m.xp_base) or 0),
        "xp_bonus": int(cast(int | None, m.xp_bonus) or 0),
        "emoji": "🎯" if required_difficulty != "easy" else "⭐",
        "route": str(cast(str | None, m.route) or ""),
        "mission_type": "topic_practice",
        "topic_id": int(cast(int | None, m.topic_id) or 0) or None,
        "lesson_id": int(cast(int | None, m.lesson_id) or 0),
        "target_count": target_count,
        "completed_count": correct_count,
        "is_completed": bool(cast(bool | None, m.is_completed) or False),
    }


def _ensure_daily_missions(db: Session, user_id: int) -> List[UserDailyMission]:
    today = dt_date.today()
    existing = (
        db.query(UserDailyMission)
        .filter(UserDailyMission.user_id == user_id, UserDailyMission.mission_date == today)
        .order_by(UserDailyMission.mission_order.asc())
        .all()
    )
    if existing:
        return existing

    service = ProgressService(db)
    recommendations = service.get_recommendations(user_id)
    weak_topics = recommendations.get("weak_topics", [])
    all_topics = db.query(Topic).order_by(Topic.id.asc()).all()
    topic_title_by_id: dict[int, str] = {
        int(cast(int | None, t.id) or 0): str(cast(str | None, t.title) or "")
        for t in all_topics
    }

    topic_ids: List[int] = [int(t["topic_id"]) for t in weak_topics if int(t.get("topic_id", 0)) > 0]
    fallback_topic_ids = [int(cast(int | None, t.id) or 0) for t in all_topics if int(cast(int | None, t.id) or 0) not in topic_ids]

    rng = Random(_seed_for_day(user_id, today))
    rng.shuffle(fallback_topic_ids)
    for tid in fallback_topic_ids:
        if len(topic_ids) >= 4:
            break
        topic_ids.append(tid)

    mission_specs = [
        ("easy", 3, 30, 15),
        ("medium", 3, 40, 20),
        ("hard", 2, 60, 30),
        ("medium", 4, 45, 20),
    ]

    created: List[UserDailyMission] = []
    for idx, topic_id in enumerate(topic_ids[:4]):
        diff_value, target_count, xp_base, xp_bonus = mission_specs[idx]
        diff_enum = DifficultyLevel(diff_value)
        lesson_id = _find_lesson_for_topic_and_difficulty(db, topic_id, diff_enum)
        if lesson_id is None:
            continue

        topic_title = topic_title_by_id.get(topic_id, f"Тема {topic_id}")
        mission_key = f"m_{today.strftime('%Y%m%d')}_{idx + 1}"
        title = f"{target_count} {_difficulty_label(diff_value).lower()} задачи: {topic_title}"
        description = f"Реши {target_count} {_difficulty_label(diff_value).lower()} задачи по темата"
        route = f"/lessons/{lesson_id}/exercises?mission_id={mission_key}"

        mission = UserDailyMission(
            user_id=user_id,
            mission_date=today,
            mission_key=mission_key,
            title=title,
            description=description,
            topic_id=topic_id,
            lesson_id=lesson_id,
            required_difficulty=diff_value,
            target_count=target_count,
            completed_count=0,
            correct_count=0,
            xp_base=xp_base,
            xp_bonus=xp_bonus,
            route=route,
            mission_order=idx,
            is_completed=False,
            xp_awarded=False,
        )
        db.add(mission)
        created.append(mission)

    db.commit()
    for mission in created:
        db.refresh(mission)
    return created


@router.get("/activity-feed")
async def get_activity_feed(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Return the most recent XP events for the activity feed."""
    resolved_user_id = _resolve_user_id(current_user, user_id)
    from app.models.progress import XpEvent as XpEventModel
    events = (
        db.query(XpEventModel)
        .filter(XpEventModel.user_id == resolved_user_id)
        .order_by(XpEventModel.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "source_type": e.source_type,
            "xp_amount": e.xp_amount,
            "reason": e.reason,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]




@router.get("/daily-missions")
async def get_daily_missions(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    resolved_user_id = _resolve_user_id(current_user, user_id)
    missions = _ensure_daily_missions(db, resolved_user_id)
    return [_serialize_mission(m) for m in missions]


@router.post("/daily-missions/track")
async def track_daily_mission_progress(
    mission_id: str,
    exercise_id: int,
    is_correct: bool,
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Track mission progress per unique exercise and award XP only when mission is fully completed."""
    resolved_user_id = _resolve_user_id(current_user, user_id)
    today = dt_date.today()
    mission = db.query(UserDailyMission).filter(
        UserDailyMission.user_id == resolved_user_id,
        UserDailyMission.mission_date == today,
        UserDailyMission.mission_key == mission_id,
    ).first()

    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found for today")

    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    lesson = db.query(Lesson).filter(Lesson.id == exercise.lesson_id).first()
    mission_lesson_id = int(cast(int | None, mission.lesson_id) or 0)
    if not lesson or int(cast(int | None, lesson.id) or 0) != mission_lesson_id:
        raise HTTPException(status_code=400, detail="Exercise is outside the selected mission lesson")

    exercise_diff = str(exercise.difficulty.value if getattr(exercise.difficulty, "value", None) else exercise.difficulty)
    if exercise_diff != mission.required_difficulty:
        return {
            "mission_id": mission_id,
            "ignored": True,
            "reason": "Difficulty mismatch for this mission",
            "target_count": mission.target_count,
            "completed_count": mission.correct_count,
            "is_completed": mission.is_completed,
            "xp_earned": 0,
        }

    existing = db.query(UserMissionExercise).filter(
        UserMissionExercise.mission_id == mission.id,
        UserMissionExercise.exercise_id == exercise_id,
    ).first()

    if existing:
        return {
            "mission_id": mission_id,
            "ignored": True,
            "reason": "Exercise already counted for this mission",
            "target_count": mission.target_count,
            "completed_count": mission.correct_count,
            "is_completed": mission.is_completed,
            "xp_earned": 0,
        }

    db.add(UserMissionExercise(
        mission_id=mission.id,
        exercise_id=exercise_id,
        is_correct=is_correct,
    ))

    current_completed_count = int(cast(int | None, mission.completed_count) or 0)
    setattr(mission, "completed_count", current_completed_count + 1)
    if is_correct:
        current_correct_count = int(cast(int | None, mission.correct_count) or 0)
        setattr(mission, "correct_count", current_correct_count + 1)

    xp_earned = 0
    mission_correct_count = int(cast(int | None, mission.correct_count) or 0)
    mission_target_count = int(cast(int | None, mission.target_count) or 0)
    if mission_correct_count >= mission_target_count:
        setattr(mission, "is_completed", True)
        if not bool(mission.xp_awarded):
            mission_multiplier = 1.5
            xp_base = int(cast(int | None, mission.xp_base) or 0)
            xp_bonus = int(cast(int | None, mission.xp_bonus) or 0)
            xp_earned = int((xp_base + xp_bonus) * mission_multiplier)
            service = ProgressService(db)
            service.award_bonus_xp(
                user_id=resolved_user_id,
                xp_amount=xp_earned,
                source_type="daily_mission",
                source_id=int(cast(int | None, mission.id) or 0),
                reason=f"Завършена мисия: {str(cast(str | None, mission.title) or '')}",
            )
            service.evaluate_and_grant_badges(resolved_user_id)
            setattr(mission, "xp_awarded", True)

    db.add(mission)
    db.commit()

    return {
        "mission_id": mission_id,
        "target_count": int(cast(int | None, mission.target_count) or 0),
        "completed_count": int(cast(int | None, mission.correct_count) or 0),
        "is_completed": bool(cast(bool | None, mission.is_completed) or False),
        "xp_earned": xp_earned,
    }


@router.get("/user-limits", response_model=UserLimitInfo)
async def get_user_limits(
    user_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's usage limits and remaining quota for freemium features.
    
    Returns:
    - plan: "free" or "premium"
    - Remaining counts for AI exercises, chat, exams, image scans
    - Days until daily reset
    """
    from app.models.user import User
    from datetime import timedelta
    
    resolved_user_id = _resolve_user_id(current_user, user_id)
    user = db.query(User).filter(User.id == resolved_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    from app.auth.dependencies import FREE_LIMITS, PREMIUM_LIMITS
    
    from app.services.billing import is_premium

    premium = is_premium(user)
    plan_value = "premium" if premium else "free"
    limits = PREMIUM_LIMITS if premium else FREE_LIMITS
    ai_exercises_used = int(cast(int | None, user.ai_exercises_today) or 0)
    ai_chat_used = int(cast(int | None, user.ai_chat_today) or 0)
    nvo_exams_used = int(cast(int | None, user.nvo_exams_today) or 0)
    image_scans_used = int(cast(int | None, user.image_scans_today) or 0)
    
    # Calculate days until reset (next midnight UTC)
    today = dt_date.today()
    next_reset = today + timedelta(days=1)
    days_until_reset = (next_reset - today).days
    
    return UserLimitInfo(
        plan=plan_value,
        
        # AI Exercises
        ai_exercises_remaining=max(0, limits["ai_exercises"] - ai_exercises_used),
        ai_exercises_limit=limits["ai_exercises"],
        ai_exercises_used_today=ai_exercises_used,
        
        # AI Chat
        ai_chat_remaining=max(0, limits["ai_chat"] - ai_chat_used),
        ai_chat_limit=limits["ai_chat"],
        ai_chat_used_today=ai_chat_used,
        
        # NVO Exams
        nvo_exams_remaining=max(0, limits["nvo_exams"] - nvo_exams_used),
        nvo_exams_limit=limits["nvo_exams"],
        nvo_exams_used_today=nvo_exams_used,

        # Image Scans
        image_scans_remaining=max(0, limits["image_scans"] - image_scans_used),
        image_scans_limit=limits["image_scans"],
        image_scans_used_today=image_scans_used,

        # Premium info
        is_premium=premium,
        can_upgrade=not premium,
        days_until_reset=days_until_reset,
    )


@router.post("/admin/reset-all-xp")
async def reset_all_xp_admin(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Admin endpoint to reset XP for all users.

    SECURITY: this used to have no auth dependency at all — any anonymous
    caller could wipe every user's XP profile and delete the entire
    xp_events table with one unauthenticated request.
    """
    try:
        # Reset all UserXpProfile records
        profiles = db.query(UserXpProfile).all()
        for profile in profiles:
            profile.total_xp = 0
            profile.streak_days = 0
            profile.streak_multiplier = 1.0
            profile.today_xp = 0
            profile.last_activity_date = None

        # Delete all XpEvent records
        deleted_events = db.query(XpEvent).delete()

        db.commit()
        return {
            "success": True,
            "message": f"Reset {len(profiles)} user XP profiles and deleted {deleted_events} XP event records"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error resetting XP: {str(e)}")

