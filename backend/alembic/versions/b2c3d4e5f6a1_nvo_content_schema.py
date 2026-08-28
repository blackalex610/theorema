"""nvo content schema

Adds the structured NVO problem corpus described in
NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 0: source exams, topic taxonomy,
skills taxonomy, the problems table itself, and their join table.

Prefixed `nvo_` — `topics` already names the practice-curriculum table in
app.models.curriculum; this is a separate taxonomy for the NVO
exam-generation corpus.

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-26 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nvo_source_exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("variant", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="official"),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="bg"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "nvo_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("grade", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_nvo_topics_code", "nvo_topics", ["code"], unique=True)

    op.create_table(
        "nvo_skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_nvo_skills_code", "nvo_skills", ["code"], unique=True)

    op.create_table(
        "nvo_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_exam_id", sa.Integer(), sa.ForeignKey("nvo_source_exams.id"), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("nvo_topics.id"), nullable=False),
        sa.Column("external_ref", sa.String(length=64), nullable=False),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("answer_format", sa.String(length=16), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("correct_answer_json", sa.Text(), nullable=False),
        sa.Column("open_parts_json", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slot_number", "external_ref", name="uq_nvo_problem_slot_ref"),
    )
    op.create_index("ix_nvo_problems_topic_id", "nvo_problems", ["topic_id"])
    op.create_index("ix_nvo_problems_slot_number", "nvo_problems", ["slot_number"])

    op.create_table(
        "nvo_problem_skills",
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("nvo_problems.id"), primary_key=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("nvo_skills.id"), primary_key=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_table("nvo_problem_skills")
    op.drop_index("ix_nvo_problems_slot_number", table_name="nvo_problems")
    op.drop_index("ix_nvo_problems_topic_id", table_name="nvo_problems")
    op.drop_table("nvo_problems")
    op.drop_index("ix_nvo_skills_code", table_name="nvo_skills")
    op.drop_table("nvo_skills")
    op.drop_index("ix_nvo_topics_code", table_name="nvo_topics")
    op.drop_table("nvo_topics")
    op.drop_table("nvo_source_exams")
