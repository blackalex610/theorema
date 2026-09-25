"""shared rate-limit counters

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("rate_limit_counters"):
        return
    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket", sa.String(length=160), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket", "window_start"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_counters")
