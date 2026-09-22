"""schools

The institutional layer: a director creates a school and gets a code,
teachers join with it, and each teacher attaches their own classes.

classrooms.school_id is nullable and SET NULL on delete: a class belongs to
its teacher, and closing a school must release its classes rather than
destroy them.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("director_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("join_code", sa.String(length=12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("join_code", name="uq_schools_join_code"),
    )
    op.create_index("ix_schools_director_id", "schools", ["director_id"])
    op.create_index("ix_schools_join_code", "schools", ["join_code"])

    op.create_table(
        "school_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("school_id", "teacher_id", name="uq_school_teacher"),
    )
    op.create_index("ix_school_members_school_id", "school_members", ["school_id"])
    op.create_index("ix_school_members_teacher_id", "school_members", ["teacher_id"])

    # SQLite cannot add a column with a foreign key in place, and this table
    # already exists in every deployment — batch_alter_table rebuilds it.
    with op.batch_alter_table("classrooms") as batch:
        batch.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_classrooms_school_id", "schools", ["school_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_classrooms_school_id", "classrooms", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_classrooms_school_id", table_name="classrooms")
    with op.batch_alter_table("classrooms") as batch:
        batch.drop_constraint("fk_classrooms_school_id", type_="foreignkey")
        batch.drop_column("school_id")

    op.drop_index("ix_school_members_teacher_id", table_name="school_members")
    op.drop_index("ix_school_members_school_id", table_name="school_members")
    op.drop_table("school_members")

    op.drop_index("ix_schools_join_code", table_name="schools")
    op.drop_index("ix_schools_director_id", table_name="schools")
    op.drop_table("schools")
