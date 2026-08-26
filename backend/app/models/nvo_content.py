"""Structured NVO problem corpus — source exams, taxonomy, and problem rows.

Implements NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 0. Prefixed `nvo_` because
`topics`/`grades` already name the practice-curriculum tables in
app.models.curriculum; this is a separate taxonomy for the NVO
exam-generation corpus, not the same rows.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class NvoSourceExam(Base):
    """Provenance record for one official/synthetic/curated NVO exam document."""

    __tablename__ = "nvo_source_exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    year = Column(Integer, nullable=True)
    variant = Column(String(32), nullable=True)
    source_type = Column(String(32), nullable=False, default="official")
    language = Column(String(8), nullable=False, default="bg")
    raw_text = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NvoTopic(Base):
    """A slot topic in the NVO taxonomy (e.g. arithmetic_expression_evaluation)."""

    __tablename__ = "nvo_topics"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    grade = Column(Integer, nullable=False, default=7)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NvoSkill(Base):
    """A fine-grained skill tag (many-to-many with problems via NvoProblemSkill).

    Not populated by the Phase 2 backfill — the current catalog has no skill
    data. Table exists so the taxonomy is ready when a skill-tagging pass
    (manual or model-assisted) is added later.
    """

    __tablename__ = "nvo_skills"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)


class NvoProblem(Base):
    """One retrievable NVO problem: a specific variant at a specific template slot."""

    __tablename__ = "nvo_problems"
    __table_args__ = (
        UniqueConstraint("slot_number", "external_ref", name="uq_nvo_problem_slot_ref"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_exam_id = Column(Integer, ForeignKey("nvo_source_exams.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("nvo_topics.id"), nullable=False, index=True)
    external_ref = Column(String(64), nullable=False)
    slot_number = Column(Integer, nullable=False, index=True)
    answer_format = Column(String(16), nullable=False)  # 'mcq' | 'open'
    statement = Column(Text, nullable=False)
    options_json = Column(Text, nullable=True)
    correct_answer_json = Column(Text, nullable=False)
    open_parts_json = Column(Text, nullable=True)
    difficulty = Column(String(16), nullable=False, default="medium")
    quality_score = Column(Float, nullable=False, default=1.0)
    is_active = Column(Boolean, nullable=False, default=True)
    content_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NvoProblemSkill(Base):
    """Many-to-many join between nvo_problems and nvo_skills."""

    __tablename__ = "nvo_problem_skills"

    problem_id = Column(Integer, ForeignKey("nvo_problems.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("nvo_skills.id"), primary_key=True)
    weight = Column(Float, nullable=False, default=1.0)
