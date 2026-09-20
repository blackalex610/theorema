"""saved_problems

Bookmarked practice exercises and NVO questions. Stores a full JSON snapshot
rather than a reference because NVO questions have no durable id and their
generated exam expires after 24h, so a reference would rot exactly when a
student wants to come back to it.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "source", "source_ref", name="uq_saved_problem_user_source_ref"
        ),
    )
    op.create_index("ix_saved_problems_user_id", "saved_problems", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_problems_user_id", table_name="saved_problems")
    op.drop_table("saved_problems")
