"""user consent record

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-25

Adds the age-group answer and consent record to users (see
app/services/consent.py). Columns are added only if missing, so a database
adopted from the old create_all() path — whose users table may already have
been built from the current model — migrates cleanly too.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _columns() -> list[sa.Column]:
    return [
        sa.Column("age_group", sa.String(length=16), nullable=True),
        sa.Column("parental_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_version", sa.String(length=32), nullable=True),
        sa.Column("consent_recorded_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    for column in _columns():
        if column.name not in existing:
            op.add_column("users", column)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in reversed(_columns()):
            batch.drop_column(column.name)
