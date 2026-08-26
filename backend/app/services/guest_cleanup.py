"""Deletes abandoned guest accounts.

Guest rows are created unauthenticated (POST /auth/guest) and have no
password/email recovery — an abandoned one is pure clutter. But `user_id`
columns across the app have NO foreign key back to `users` (see the model
comments "Will link to User model later"), so deleting a user neither
cascades nor errors: a guest row that DOES have activity must be excluded
explicitly here, or its child rows are silently orphaned.

Exposed only behind an admin-gated endpoint for now (no scheduler wired up
yet) — see POST /auth/admin/purge-guests in app.routers.auth.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.models.curriculum import ExerciseAttempt
from app.models.progress import (
    LessonProgress,
    UserBadge,
    UserDailyMission,
    UserProgress,
    UserXpProfile,
    XpEvent,
)
from app.models.user import User

# Every table that carries a user_id today. If a new one is added, it must be
# added here too, or a guest with only that kind of activity gets purged.
_ACTIVITY_TABLES = (
    ExerciseAttempt,
    UserProgress,
    LessonProgress,
    UserXpProfile,
    XpEvent,
    UserBadge,
    UserDailyMission,
)


def purge_stale_guests(db: Session, older_than_days: int = 30) -> int:
    """Delete guest users older than `older_than_days` with zero activity.

    Returns the number of rows deleted. Never touches a non-guest user or a
    guest with any row in _ACTIVITY_TABLES, regardless of age.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    candidates = (
        db.query(User)
        .filter(User.is_guest.is_(True), User.created_at < cutoff)
        .all()
    )

    deleted = 0
    for user in candidates:
        has_activity = any(
            db.query(exists().where(table.user_id == user.id)).scalar()
            for table in _ACTIVITY_TABLES
        )
        if has_activity:
            continue
        db.delete(user)
        deleted += 1

    if deleted:
        db.commit()
    return deleted
