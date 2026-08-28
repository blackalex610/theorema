"""nvo generation runs

Audit trail for NVO_CONTENT_ARCHITECTURE_PLAN.md Phase 3: one row per
generation call recording whether it was served from the DB corpus or the
file catalog fallback.

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-08-26 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nvo_generation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requested_profile_json", sa.Text(), nullable=False),
        sa.Column("selected_problem_ids_json", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("validation_report_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("nvo_generation_runs")
