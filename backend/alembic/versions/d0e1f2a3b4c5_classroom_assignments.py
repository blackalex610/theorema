"""classroom assignments

One generated paper pinned to one class, so the whole class sits the same
questions and per-question comparison across a class becomes possible.

No submissions table by design: nvo_attempts already carries
UNIQUE(user_id, exam_id), so "did this student sit it" is a query against
the data that is already the source of truth for scoring.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classroom_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("classroom_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        # The pinned paper. services/assignment_service extends this exam's
        # expires_at past the due date, because generated exams are otherwise
        # 24h cache rows that get purged.
        sa.Column("exam_id", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=True),
        sa.Column("format", sa.String(length=16), nullable=True),
        sa.Column("blueprint", sa.String(length=32), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_classroom_assignments_classroom_id", "classroom_assignments", ["classroom_id"]
    )
    op.create_index(
        "ix_classroom_assignments_teacher_id", "classroom_assignments", ["teacher_id"]
    )
    op.create_index("ix_classroom_assignments_exam_id", "classroom_assignments", ["exam_id"])


def downgrade() -> None:
    op.drop_index("ix_classroom_assignments_exam_id", table_name="classroom_assignments")
    op.drop_index("ix_classroom_assignments_teacher_id", table_name="classroom_assignments")
    op.drop_index("ix_classroom_assignments_classroom_id", table_name="classroom_assignments")
    op.drop_table("classroom_assignments")
