"""nvo attempt items

Per-question results for a graded attempt. /nvo/submit already decided each
question's outcome and kept only the three totals, so class-level diagnostics
("which topics is this class failing") were impossible and could not be
backfilled — the generated paper is a GeneratedExam row with a 24h TTL.

`topic_key` stores the canonical key from app/services/nvo_topics, not the
raw generator label: the catalog and the blueprint generator spell the same
mathematics differently.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-22 00:00:00

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
        "nvo_attempt_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        # Denormalised from the parent attempt so that erasure (which is
        # driven by user_id, because nothing in this schema cascades) reaches
        # these rows, and so a per-student topic profile is a single scan.
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("topic_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="mc"),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("points_awarded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_max", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["nvo_attempts.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "attempt_id", "question_number", name="uq_nvo_attempt_item_question"
        ),
    )
    op.create_index("ix_nvo_attempt_items_attempt_id", "nvo_attempt_items", ["attempt_id"])
    op.create_index("ix_nvo_attempt_items_user_id", "nvo_attempt_items", ["user_id"])
    op.create_index("ix_nvo_attempt_items_topic_key", "nvo_attempt_items", ["topic_key"])


def downgrade() -> None:
    op.drop_index("ix_nvo_attempt_items_topic_key", table_name="nvo_attempt_items")
    op.drop_index("ix_nvo_attempt_items_user_id", table_name="nvo_attempt_items")
    op.drop_index("ix_nvo_attempt_items_attempt_id", table_name="nvo_attempt_items")
    op.drop_table("nvo_attempt_items")
