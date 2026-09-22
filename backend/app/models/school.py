"""Schools — the level a building's director buys at.

This repeats, one level up, the two decisions that made classrooms work
(see models/classroom.py), because they were right for the same reasons:

* **There is no `role` column.** You are the director of the school you
  created and a teacher of the schools you joined, exactly as you teach the
  classes you created and attend the ones you joined.
* **The join code is the consent record.** A director cannot pull a teacher
  into a school; the teacher types the code. And a teacher's *class* is
  attached by that teacher, not by the director — so a child who consented
  to one teacher seeing their work is not enrolled into a building-wide
  report by someone they have never met.

What a director can see is therefore deliberately narrower than what a
teacher sees: cohort and class-level aggregates, never another teacher's
individual students. That boundary is enforced in services/school_service
and pinned in tests/test_schools.py.
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


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    # The user who created it. No FK, consistent with every other user
    # reference in this schema; erasure is explicit in services/user_data.py.
    director_id = Column(Integer, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    city = Column(String(120), nullable=True)
    join_code = Column(String(12), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SchoolMember(Base):
    """A teacher who joined a school. Timestamped, like a class join."""

    __tablename__ = "school_members"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id = Column(Integer, nullable=False, index=True)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("school_id", "teacher_id", name="uq_school_teacher"),
    )
