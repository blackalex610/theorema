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
    # Set by the teacher who owns this class when they attach it to a school
    # they have joined — never by the director. A class with no school is the
    # normal case and stays fully functional; the school layer is additive.
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


class ClassroomAssignment(Base):
    """One paper, assigned to one class.

    `exam_id` pins a single generated paper that **every student in the class
    sits**. That is the whole point: per-question comparison across a class
    ("17 of 26 missed question 7") is only a sentence anyone can say when
    everyone answered the same question 7. The cost is that students can copy
    from each other, which is a decision for the teacher setting the window,
    not something the schema should pretend to solve.

    There is deliberately **no submissions table**. `nvo_attempts` already
    carries UNIQUE(user_id, exam_id), so "did this student sit it" is a query
    against data that is already the source of truth for scoring. A second
    table would be a second thing to keep in step, and the audit's recurring
    finding in this codebase is registries that drift.

    A generated exam is normally a 24h cache row. Assigning one extends that
    row's `expires_at` past the due date — see services/assignment_service.
    """

    __tablename__ = "classroom_assignments"

    id = Column(Integer, primary_key=True, index=True)
    classroom_id = Column(
        Integer, ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised from the classroom so erasure can find a teacher's
    # assignments without a join, consistent with the rest of this schema.
    teacher_id = Column(Integer, nullable=False, index=True)
    title = Column(String(160), nullable=False)
    exam_id = Column(String(64), nullable=False, index=True)
    difficulty = Column(String(16), nullable=True)
    format = Column(String(16), nullable=True)
    blueprint = Column(String(32), nullable=True)
    due_at = Column(DateTime, nullable=True)
    # Closed rather than deleted: the term's record of what was set, and what
    # came back, should survive the assignment being over.
    is_open = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
