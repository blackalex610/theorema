"""event logs

Shared table backing analytics events, bug reports, feedback submissions and
error logs — replaces four backend/logs/*.jsonl files, which live inside the
deployment bundle and are read-only (and therefore silently no-op) on
Vercel.

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-09-11 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, None] = "e5f6a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("log_type", sa.String(length=20), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_event_logs_log_type", "event_logs", ["log_type"])
    op.create_index("ix_event_logs_created_at", "event_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_event_logs_created_at", table_name="event_logs")
    op.drop_index("ix_event_logs_log_type", table_name="event_logs")
    op.drop_table("event_logs")
