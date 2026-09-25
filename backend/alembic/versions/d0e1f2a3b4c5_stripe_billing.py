"""stripe billing columns

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-25

Subscription state on users (see app/services/billing.py). Idempotent, like
c9d0e1f2a3b4, so an adopted pre-Alembic database migrates cleanly.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_users_stripe_customer_id"


def _columns() -> list[sa.Column]:
    return [
        sa.Column("stripe_customer_id", sa.String(length=64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("subscription_status", sa.String(length=32), nullable=True),
        sa.Column("premium_until", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("users")}
    for column in _columns():
        if column.name not in existing:
            op.add_column("users", column)
    if _INDEX not in {index["name"] for index in inspector.get_indexes("users")}:
        op.create_index(_INDEX, "users", ["stripe_customer_id"], unique=True)


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="users")
    with op.batch_alter_table("users") as batch:
        for column in reversed(_columns()):
            batch.drop_column(column.name)
