"""guest users

Adds real, durable guest accounts: makes `google_sub`/`email` nullable (a
guest has neither — Postgres treats NULLs as distinct under a UNIQUE
constraint, so this needs no relaxation of the constraint itself) and adds
`is_guest`/`upgraded_at` plus a composite index used by both the per-IP
guest-flood cap and the stale-guest reaper.

Revision ID: a1b2c3d4e5f6
Revises: 754e61405945
Create Date: 2026-08-25 23:16:38

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "754e61405945"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "google_sub", existing_type=sa.String(length=128), nullable=True)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.add_column(
        "users",
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("upgraded_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_users_guest_ip_created",
        "users",
        ["is_guest", "last_login_ip", "created_at"],
    )


def downgrade() -> None:
    # Irreversible while guest rows exist (they violate NOT NULL) — delete
    # them first: DELETE FROM users WHERE is_guest;
    op.drop_index("ix_users_guest_ip_created", table_name="users")
    op.drop_column("users", "upgraded_at")
    op.drop_column("users", "is_guest")
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "google_sub", existing_type=sa.String(length=128), nullable=False)
