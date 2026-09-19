"""classrooms

The link between an adult and a student's real progress — the foundation
under both the teacher product and the parent product. There is deliberately
no `role` column on users: a person teaches the classes they created and
attends the ones they joined.

`classroom_members.joined_at` doubles as the consent record: a teacher cannot
add a student, the student enters the join code themselves.

Revision ID: a7b8c9d0e1f2
Revises: f6a1b2c3d4e5
Create Date: 2026-09-13 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classrooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("join_code", sa.String(length=12), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("join_code", name="uq_classroom_join_code"),
    )
    op.create_index("ix_classrooms_teacher_id", "classrooms", ["teacher_id"])
    op.create_index("ix_classrooms_join_code", "classrooms", ["join_code"])

    op.create_table(
        "classroom_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("classroom_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["classrooms.id"],
            name="fk_classroom_members_classroom", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),
    )
    op.create_index("ix_classroom_members_classroom_id", "classroom_members", ["classroom_id"])
    op.create_index("ix_classroom_members_student_id", "classroom_members", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_classroom_members_student_id", table_name="classroom_members")
    op.drop_index("ix_classroom_members_classroom_id", table_name="classroom_members")
    op.drop_table("classroom_members")
    op.drop_index("ix_classrooms_join_code", table_name="classrooms")
    op.drop_index("ix_classrooms_teacher_id", table_name="classrooms")
    op.drop_table("classrooms")
