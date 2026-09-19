"""mobile channel state

Moves the desktop<->phone pairing channel's shared state out of module-level
dicts in app/routers/mobile_uploads.py and into the database.

Those dicts made the pairing feature serverless-fatal: the desktop registers a
problem's answer key with POST /mobile/tasks/context, then the phone calls
POST /mobile/tasks/grade-photo — a different request that lands on a different
instance, whose task_contexts dict was empty, so it returned 404. The same
split broke GET /mobile/uploads/latest, which the desktop polls for photos the
phone pushed.

Both tables are disposable cache entries with an explicit expires_at on the
same clock as media retention (the uploaded file itself is purged at that age).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-19 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_upload_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_mobile_upload_records_channel_id", "mobile_upload_records", ["channel_id"])
    op.create_index("ix_mobile_upload_records_uploaded_at", "mobile_upload_records", ["uploaded_at"])
    op.create_index("ix_mobile_upload_records_expires_at", "mobile_upload_records", ["expires_at"])

    op.create_table(
        "mobile_task_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.String(length=64), nullable=False),
        sa.Column("problem_number", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("channel_id", "problem_number", name="uq_mobile_task_context"),
    )
    op.create_index("ix_mobile_task_contexts_channel_id", "mobile_task_contexts", ["channel_id"])
    op.create_index("ix_mobile_task_contexts_expires_at", "mobile_task_contexts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_mobile_task_contexts_expires_at", table_name="mobile_task_contexts")
    op.drop_index("ix_mobile_task_contexts_channel_id", table_name="mobile_task_contexts")
    op.drop_table("mobile_task_contexts")

    op.drop_index("ix_mobile_upload_records_expires_at", table_name="mobile_upload_records")
    op.drop_index("ix_mobile_upload_records_uploaded_at", table_name="mobile_upload_records")
    op.drop_index("ix_mobile_upload_records_channel_id", table_name="mobile_upload_records")
    op.drop_table("mobile_upload_records")
