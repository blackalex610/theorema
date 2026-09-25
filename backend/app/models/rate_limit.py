"""Shared rate-limit counters (app/middleware/ip_rate_limiter.py).

One row per (bucket, fixed time window). The counts used to live in a dict in
each process, and on Vercel every serverless instance has its own process —
a burst spread over instances was never limited at all.
"""
from sqlalchemy import BigInteger, Column, Integer, String

from app.database import Base


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    bucket = Column(String(160), primary_key=True)          # "<ip>:<tier>"
    window_start = Column(BigInteger, primary_key=True)     # epoch seconds
    hits = Column(Integer, nullable=False, default=0)
