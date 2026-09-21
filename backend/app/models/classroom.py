"""Classrooms — the link between an adult and a student's real progress.

This is the foundation under both the teacher product and (later) the parent
product: in both cases an adult needs to see work that belongs to a child,
and in both cases that is only lawful if the child opted in.

Two deliberate decisions:

* **There is no `role` column.** A user is the teacher of the classes they
  created and a student of the classes they joined. Teacher-ness as mutable
  account state would be one more thing to get wrong (and to have to migrate,
  and to have to gate), for no behaviour this product needs.
* **The join code is the consent record.** A teacher cannot add a student;
  the student enters the code. `joined_at` is therefore a timestamped record
  of when that child agreed to be visible to that teacher.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class Classroom(Base):
    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, index=True)
    # The user who created it. No FK, consistent with every other user_id in
    # this schema; erasure is handled explicitly in services/user_data.py.
    teacher_id = Column(Integer, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    join_code = Column(String(12), nullable=False, unique=True, index=True)
    grade_level = Column(Integer, nullable=True)  # 5, 6 or 7 where it applies
    # Archived rather than deleted: a class that has finished should stop
    # accepting joins without destroying the term's record of who was in it.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ClassroomMember(Base):
    __tablename__ = "classroom_members"

    id = Column(Integer, primary_key=True, index=True)
    classroom_id = Column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id = Column(Integer, nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_classroom_student"),
    )
