"""Problems a student has bookmarked to come back to later.

The snapshot is the whole point. A practice exercise has a durable row id, but
an NVO question does not: its id is only the ordinal within a generated exam,
and that exam is evicted from the store after 24h. Saving a reference would
leave a dead entry exactly when the student wants to revisit it, so the full
question payload is copied in here at save time instead.

Both sources normalise onto one snapshot schema so the review page needs a
single renderer — see docs/superpowers/specs/2026-09-20-saved-problems-design.md.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.database import Base


class SavedProblem(Base):
    """One bookmarked problem. Real user data, no TTL."""

    __tablename__ = "saved_problems"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    # "exercise" | "nvo"
    source = Column(String(16), nullable=False)
    # Dedupe key: str(exercise_id), or f"{exam_id}:{question_number}".
    # A single non-null string rather than nullable typed columns, because SQL
    # treats NULLs as distinct and a composite key over them would silently
    # fail to dedupe.
    source_ref = Column(String(128), nullable=False)
    snapshot_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "source_ref", name="uq_saved_problem_user_source_ref"
        ),
    )
