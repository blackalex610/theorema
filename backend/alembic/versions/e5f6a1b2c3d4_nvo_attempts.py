"""nvo attempts

Server-side record of a graded NVO exam attempt. Previously MCQ scoring and
the final percentage were computed client-side and posted to /nvo/award-xp
as plain numbers; this table is the server's own scoring record, the source
of truth for award-xp, and what makes the award idempotent per attempt.

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-09-11 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a1b2c3d4"
down_revision: Union[str, None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nvo_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.String(length=64), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False, server_default="standard"),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="full"),
        sa.Column("mcq_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mcq_max_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("open_max_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percentage_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp_awarded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("xp_result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("graded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "exam_id", name="uq_nvo_attempt_user_exam"),
    )
    op.create_index("ix_nvo_attempts_user_id", "nvo_attempts", ["user_id"])
    op.create_index("ix_nvo_attempts_exam_id", "nvo_attempts", ["exam_id"])


def downgrade() -> None:
    op.drop_index("ix_nvo_attempts_exam_id", table_name="nvo_attempts")
    op.drop_index("ix_nvo_attempts_user_id", table_name="nvo_attempts")
    op.drop_table("nvo_attempts")
