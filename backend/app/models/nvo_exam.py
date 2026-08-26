"""Durable storage for generated NVO exams and their generation jobs.

Both of these used to live only in module-level dicts inside
``app.routers.nvo``. That works on a single long-lived process and fails
completely on serverless (Vercel): the request that generates an exam and the
request that later fetches it can land on different instances, so
``GET /nvo/generated/{exam_id}`` and ``GET /nvo/generate-job/{job_id}``
returned 404 for an exam that had just been generated successfully.

Rows here are disposable cache entries with an explicit ``expires_at``, not
long-lived user data — see ``app.services.nvo_exam_store`` for the read/write
path and the purge.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class GeneratedExam(Base):
    """A generated exam, serialised as JSON, keyed by its short exam id."""

    __tablename__ = "generated_exams"

    exam_id = Column(String(64), primary_key=True, index=True)
    questions_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class NVOGenerationJob(Base):
    """Progress of one exam-generation run, polled by the client."""

    __tablename__ = "nvo_generation_jobs"

    job_id = Column(String(64), primary_key=True, index=True)
    status = Column(String(32), nullable=False)
    progress = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=False, default="")
    exam_id = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
