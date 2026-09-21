"""nvo problem embeddings

Phase 4 (hybrid retrieval): cached embedding vectors per problem, stored as
JSON text rather than a native vector column so the same schema works on
SQLite (the test suite's only dialect) and Postgres without a pgvector
dependency.

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-08-26 00:00:02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nvo_problem_embeddings",
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("nvo_problems.id"), primary_key=True),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
        sa.Column("embedded_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("nvo_problem_embeddings")
