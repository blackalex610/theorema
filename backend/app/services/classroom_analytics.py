"""Turning a class's graded questions into something a teacher can act on.

The roster (classroom_service.build_roster) answers "how is this student
doing": XP, level, average exam score. It cannot answer the question a
teacher actually has on Sunday evening — *what do I reteach on Monday* —
because a percentage does not say which mathematics went wrong.

This module answers that from nvo_attempt_items, aggregated per canonical
topic and per curriculum strand.

Most of the care here is about not misleading anyone:

* **A small sample is not evidence.** A topic asked twice across a class
  can read 0% and mean nothing. Only topics asked at least
  ``MIN_ASKED_FOR_RANKING`` times are eligible to be named a weakness;
  everything is still shown in the full table, with its sample size, so the
  teacher can judge.
* **``other`` is never a recommendation.** Questions whose topic the
  taxonomy did not recognise are a signal that our labelling has drifted,
  not a topic anyone can teach.
* **A class's numbers contain only that class.** Every query is filtered to
  current members, and reading any of it requires owning the class.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.classroom import ClassroomMember
from app.models.nvo_exam import NvoAttempt, NvoAttemptItem
from app.models.user import User
from app.services import nvo_topics
from app.services.classroom_service import _owned_classroom, list_members

#: Below this many questions asked, a topic is reported but never ranked as
#: a weakness. Three is deliberately low — a class of 25 reaches it on a
#: single sitting — but it is enough to stop one careless answer becoming a
#: lesson plan.
MIN_ASKED_FOR_RANKING = 3

#: How many topics to name in each direction. A list of twenty "weaknesses"
#: is not a teaching decision, it is the same table sorted.
RANKING_SIZE = 5


def _percent(correct: int, asked: int) -> int:
    return round(100 * correct / asked) if asked else 0


def _topic_rows(db: Session, student_ids: list[int]) -> list[dict[str, Any]]:
    """Per-topic totals across a set of students, newest data included.

    One grouped query rather than a loop over students: a class is 25-30
    people and this is the page a teacher opens most.
    """
    if not student_ids:
        return []

    rows = (
        db.query(
            NvoAttemptItem.topic_key.label("topic_key"),
            func.count(NvoAttemptItem.id).label("asked"),
            func.sum(case((NvoAttemptItem.is_correct.is_(True), 1), else_=0)).label("correct"),
            func.count(func.distinct(NvoAttemptItem.user_id)).label("students"),
        )
        .filter(NvoAttemptItem.user_id.in_(student_ids))
        .group_by(NvoAttemptItem.topic_key)
        .all()
    )

    topics: list[dict[str, Any]] = []
    for row in rows:
        asked = int(row.asked or 0)
        correct = int(row.correct or 0)
        strand = nvo_topics.strand_of(row.topic_key)
        topics.append(
            {
                "key": row.topic_key,
                "label": nvo_topics.label(row.topic_key),
                "strand": strand,
                "strand_label": nvo_topics.strand_label(strand) if strand else nvo_topics.OTHER_LABEL_BG,
                "asked": asked,
                "correct": correct,
                "percent_correct": _percent(correct, asked),
                "students": int(row.students or 0),
            }
        )

    # Weakest first: this table is read to find problems, so the problems go
    # at the top rather than making the teacher sort it.
    topics.sort(key=lambda t: (t["percent_correct"], -t["asked"]))
    return topics


def _strand_rows(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, int]] = {}
    for topic in topics:
        strand = topic["strand"]
        if not strand:
            # `other` has no strand — it is not curriculum, so rolling it up
            # would put unidentified questions inside a real strand's number.
            continue
        bucket = totals.setdefault(strand, {"asked": 0, "correct": 0})
        bucket["asked"] += topic["asked"]
        bucket["correct"] += topic["correct"]

    strands = [
        {
            "key": key,
            "label": nvo_topics.strand_label(key),
            "asked": value["asked"],
            "correct": value["correct"],
            "percent_correct": _percent(value["correct"], value["asked"]),
        }
        for key, value in totals.items()
    ]
    strands.sort(key=lambda s: (s["percent_correct"], -s["asked"]))
    return strands


def _rankable(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        t
        for t in topics
        if t["key"] != nvo_topics.OTHER and t["asked"] >= MIN_ASKED_FOR_RANKING
    ]


def build_class_diagnostics(
    db: Session, *, classroom_id: int, teacher_id: int
) -> dict[str, Any]:
    """Topic-level picture of one class, for the teacher who owns it."""
    _owned_classroom(db, classroom_id, teacher_id)

    student_ids = [m.student_id for m in list_members(db, classroom_id)]
    topics = _topic_rows(db, student_ids)
    rankable = _rankable(topics)

    attempts = 0
    students_with_data = 0
    if student_ids:
        attempts = (
            db.query(func.count(NvoAttempt.id))
            .filter(NvoAttempt.user_id.in_(student_ids))
            .scalar()
            or 0
        )
        students_with_data = (
            db.query(func.count(func.distinct(NvoAttemptItem.user_id)))
            .filter(NvoAttemptItem.user_id.in_(student_ids))
            .scalar()
            or 0
        )

    return {
        "student_count": len(student_ids),
        "students_with_data": int(students_with_data),
        "attempts": int(attempts),
        "min_asked_for_ranking": MIN_ASKED_FOR_RANKING,
        "topics": topics,
        "strands": _strand_rows(topics),
        "weakest": rankable[:RANKING_SIZE],
        "strongest": list(reversed(rankable))[:RANKING_SIZE],
    }


def _member_or_404(db: Session, classroom_id: int, student_id: int) -> ClassroomMember:
    """A student actually in this class, or a 404.

    Without this, a teacher who owns any class could read any child's topic
    profile by putting someone else's id in the URL.
    """
    member = (
        db.query(ClassroomMember)
        .filter(
            ClassroomMember.classroom_id == classroom_id,
            ClassroomMember.student_id == student_id,
        )
        .one_or_none()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Ученикът не е в този клас.")
    return member


def build_student_profile(
    db: Session, *, classroom_id: int, teacher_id: int, student_id: int
) -> dict[str, Any]:
    """One student's topic profile and sitting history, for their teacher."""
    _owned_classroom(db, classroom_id, teacher_id)
    member = _member_or_404(db, classroom_id, student_id)

    user = db.query(User).filter(User.id == student_id).one_or_none()
    topics = _topic_rows(db, [student_id])

    attempts = (
        db.query(NvoAttempt)
        .filter(NvoAttempt.user_id == student_id)
        .order_by(NvoAttempt.created_at.desc())
        .all()
    )

    return {
        "student_id": student_id,
        "name": getattr(user, "name", None) or "Ученик",
        "joined_at": member.joined_at.isoformat(),
        "min_asked_for_ranking": MIN_ASKED_FOR_RANKING,
        "topics": topics,
        "weakest": _rankable(topics)[:RANKING_SIZE],
        "attempts": [
            {
                "exam_id": attempt.exam_id,
                "difficulty": attempt.difficulty,
                "format": attempt.format,
                "percentage_correct": attempt.percentage_correct,
                "created_at": attempt.created_at.isoformat(),
            }
            for attempt in attempts
        ],
    }
