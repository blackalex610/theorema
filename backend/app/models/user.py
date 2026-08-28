from sqlalchemy import Boolean, Column, Integer, String, DateTime, Date, sql
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Nullable: a guest user (is_guest=True) has neither. Postgres/SQLite
    # treat NULLs as distinct under a UNIQUE constraint, so any number of
    # guest rows can coexist without relaxing the constraint itself.
    google_sub = Column(String(128), unique=True, index=True, nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    name = Column(String(255))
    picture = Column(String(500))
    plan = Column(String(20), default="free", nullable=False)
    is_admin = Column(Integer, default=0, nullable=False)  # 0 = regular, 1 = admin
    is_guest = Column(Boolean, default=False, nullable=False, server_default=sql.false())
    upgraded_at = Column(DateTime, nullable=True)  # set when a guest links a Google account

    # Daily usage counters (reset each calendar day)
    ai_exercises_today  = Column(Integer, default=0, nullable=False)
    ai_chat_today       = Column(Integer, default=0, nullable=False)
    ai_theory_today     = Column(Integer, default=0, nullable=False)
    nvo_exams_today     = Column(Integer, default=0, nullable=False)
    image_scans_today   = Column(Integer, default=0, nullable=False)
    usage_reset_date    = Column(Date, nullable=True)

    # Chat cooldown: UTC timestamp of last AI chat message
    last_ai_chat_at = Column(DateTime, nullable=True)
    # Theory generation cooldown
    last_ai_theory_at = Column(DateTime, nullable=True)

    # Security / abuse tracking
    last_login_ip = Column(String(45), nullable=True)   # IPv4 or IPv6

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
