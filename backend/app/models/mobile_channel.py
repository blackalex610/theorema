"""Durable storage for the desktop↔phone pairing channel's shared state.

Both of these used to live only in module-level dicts inside
``app.routers.mobile_uploads``. That works on a single long-lived process and
fails completely on serverless (Vercel), where the two halves of the flow are
*by design* different requests from different devices:

* the desktop calls ``POST /mobile/tasks/context`` to register a problem's
  answer key, then the phone calls ``POST /mobile/tasks/grade-photo`` — on a
  different instance, which had an empty ``task_contexts`` and returned
  ``404 Task context not found``, so phone grading simply never worked;
* the phone calls ``POST /mobile/uploads``, then the desktop polls
  ``GET /mobile/uploads/latest`` — again a different instance, whose
  ``upload_history`` was empty, so the photo never appeared.

Rows here are disposable cache entries with an explicit ``expires_at``, not
long-lived user data. The clock deliberately matches media retention: the
uploaded file these rows describe is purged at the same age, so keeping the
metadata any longer would only ever point at a file that no longer exists.

See ``app.services.channel_state_store`` for the read/write path and the purge.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.database import Base


class MobileUploadRecord(Base):
    """One photo the phone pushed into a channel, newest-first by uploaded_at."""

    __tablename__ = "mobile_upload_records"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


class MobileTaskContext(Base):
    """The statement and answer key for one problem on one channel.

    Unique per (channel, problem): re-registering a problem replaces it rather
    than stacking a second answer key the grader might pick between.
    """

    __tablename__ = "mobile_task_contexts"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String(64), nullable=False, index=True)
    problem_number = Column(Integer, nullable=False)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("channel_id", "problem_number", name="uq_mobile_task_context"),
    )
