"""One row per analytics event, bug report, feedback submission, or error
log entry — see app.services.event_log_store for the read/write path.

SECURITY / RELIABILITY: analytics.py, bug_report.py, feedback.py and
error_logger.py used to each append to their own backend/logs/*.jsonl file.
That directory lives inside the deployment bundle, which is read-only on
Vercel — every write there silently failed, and the callers' own
`except OSError: return {"success": False}` meant production telemetry
simply never existed with no visible error anywhere. One shared table
persists like every other piece of real data in this app.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    # 'analytics' | 'bug_report' | 'feedback' | 'error' — one table, several
    # producers, so a single index serves every reader's "recent N of mine".
    log_type = Column(String(20), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
