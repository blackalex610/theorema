"""Durable storage for generated NVO exams and their generation jobs.

Both of these used to live only in module-level dicts inside
``app.routers.nvo``. That works on a single long-lived process and fails
completely on serverless (Vercel): the request that generates an exam and the
request that later fetches it can land on different instances, so
``GET /nvo/generated/{exam_id}`` and ``GET /nvo/generate-job/{job_id}``
returned 404 for an exam that had just been generated successfully.

Rows here are disposable cache entries with an explicit ``expires_at``, not
long-lived user data — see ``app.services.nvo_exam_store`` for the read/write
path and the purge.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class GeneratedExam(Base):
    """A generated exam, serialised as JSON, keyed by its short exam id."""

    __tablename__ = "generated_exams"

    exam_id = Column(String(64), primary_key=True, index=True)
    questions_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class NVOGenerationJob(Base):
    """Progress of one exam-generation run, polled by the client."""

    __tablename__ = "nvo_generation_jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    status = Column(String(32), nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=False, default="")
    exam_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class NvoAttempt(Base):
    """A student's graded attempt at one generated exam.

    Unlike GeneratedExam/NVOGenerationJob above, this is real user data with
    no TTL — it is the server's own record of how an exam was scored, and the
    single source of truth for /nvo/award-xp.

    SECURITY: this table exists because /nvo/submit used to grade only the
    open-ended questions server-side; MCQ scoring and the final percentage
    were computed entirely client-side and posted to /nvo/award-xp as plain
    numbers with no way for the server to verify them. Now /nvo/submit grades
    every question (MCQ included) and writes the result here; /nvo/award-xp
    reads it back instead of trusting the request body, and xp_awarded makes
    the award idempotent per attempt.
    """

    __tablename__ = "nvo_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    exam_id = Column(String(64), nullable=False, index=True)
    difficulty = Column(String(16), nullable=False, default="standard")
    format = Column(String(16), nullable=False, default="full")
    mcq_score = Column(Integer, nullable=False, default=0)
    mcq_max_score = Column(Integer, nullable=False, default=0)
    open_score = Column(Integer, nullable=False, default=0)
    open_max_score = Column(Integer, nullable=False, default=0)
    percentage_correct = Column(Integer, nullable=False, default=0)
    # Set once /nvo/award-xp has actually granted XP for this attempt; the
    # cached result below lets a retry return the same answer instead of
    # granting XP a second time.
    xp_awarded = Column(Boolean, nullable=False, default=False)
    xp_result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    graded_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "exam_id", name="uq_nvo_attempt_user_exam"),
    )


class NvoAttemptItem(Base):
    """One graded question inside one attempt.

    /nvo/submit already decided, question by question, whether the student
    was right — and then kept only the three totals on NvoAttempt. That made
    "Мария: 62%" answerable and "half the class falls over on inequalities"
    permanently unanswerable: the paper itself is a GeneratedExam row with a
    24h TTL, so nothing could be reconstructed after the fact. Every teacher-
    and school-facing diagnostic in the product reads these rows.

    `topic_key` is the CANONICAL key from services/nvo_topics, never the raw
    generator string: the catalog and the blueprint generator spell the same
    mathematics differently, so aggregating on the raw value would split one
    topic into two columns of a teacher's heatmap.

    `user_id` is denormalised off the parent attempt deliberately. No user_id
    in this schema carries a foreign key and nothing cascades, so erasure is
    driven by services/user_data.py reading this column — and the per-student
    topic profile becomes a single-table scan rather than a join.
    """

    __tablename__ = "nvo_attempt_items"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(
        Integer, ForeignKey("nvo_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, nullable=False, index=True)
    question_number = Column(Integer, nullable=False)
    #: Canonical key, or "other" when the taxonomy did not recognise the
    #: generator's label. Never a guess — see services/nvo_topics.resolve.
    topic_key = Column(String(64), nullable=False, index=True)
    #: "mc" | "short" | "open".
    kind = Column(String(16), nullable=False, default="mc")
    is_correct = Column(Boolean, nullable=False, default=False)
    points_awarded = Column(Integer, nullable=False, default=0)
    points_max = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_number", name="uq_nvo_attempt_item_question"),
    )
