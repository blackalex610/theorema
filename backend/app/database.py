from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool
import logging
import os
from app.config import settings

logger = logging.getLogger(__name__)

def _resolve_database_url() -> str:
    database_url = settings.DATABASE_URL
    # Vercel file system is read-only except /tmp. If sqlite is used without an
    # external DB URL, move it to /tmp to prevent write failures on auth upserts.
    if os.getenv("VERCEL") and database_url.startswith("sqlite"):
        return "sqlite:////tmp/mathlearning.db"
    return database_url


DATABASE_URL = _resolve_database_url()

# Create database engine
# SQLite requires connect_args for thread safety
# Vercel serverless requires NullPool to avoid connection exhaustion
_is_vercel = bool(os.getenv("VERCEL"))
_is_sqlite = DATABASE_URL.startswith("sqlite")
# Without this, a flaky path to the DB host (e.g. an unreliable IPv6 route)
# hangs for the OS's default TCP timeout — 20-30+ seconds — on every single
# request, since _ensure_db_tables() retries the connection from inside a
# request-path middleware. Failing fast turns that into a quick 503 instead.
connect_args = {"check_same_thread": False} if _is_sqlite else {"connect_timeout": 5}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    # NullPool: don't persist connections between serverless invocations
    **({"poolclass": NullPool} if _is_vercel and not _is_sqlite else {}),
)

# Create session local class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models (SQLAlchemy 2.0+ style)
class Base(DeclarativeBase):
    pass


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_USER_USAGE_COLUMN_MIGRATIONS = (
    "ALTER TABLE users ADD COLUMN ai_theory_today INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN last_ai_theory_at TIMESTAMP",
    "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN is_guest BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN upgraded_at TIMESTAMP",
    # NOTE: this cannot relax the pre-existing NOT NULL on google_sub/email for
    # a database that predates guest accounts (SQLite can't ALTER a column's
    # nullability; Postgres needs a separate ALTER COLUMN ... DROP NOT NULL,
    # done in the Alembic guest-users migration). A stale local SQLite file
    # created before this change should be deleted and let create_all rebuild
    # it; Postgres deployments must run the Alembic migration.
)


def _is_duplicate_column_error(exc: Exception) -> bool:
    """True when an ALTER failed only because the column is already there."""
    message = str(getattr(exc, "orig", exc)).lower()
    return any(
        marker in message
        for marker in (
            "duplicate column",       # SQLite
            "already exists",         # PostgreSQL
            "duplicate column name",  # MySQL
        )
    )


def _add_missing_user_columns(conn) -> None:
    existing = {column["name"] for column in inspect(conn).get_columns("users")}
    for stmt in _USER_USAGE_COLUMN_MIGRATIONS:
        column = stmt.split("ADD COLUMN ", 1)[1].split()[0]
        if column in existing:
            continue
        try:
            conn.execute(text(stmt))
        except Exception as exc:
            # Only reachable when another process added the column between
            # the inspect above and this ALTER.
            if _is_duplicate_column_error(exc):
                continue
            logger.error("User usage column migration failed: %s", stmt, exc_info=True)
            raise


def ensure_user_usage_columns(conn=None) -> None:
    """Add newer usage columns on existing databases (idempotent).

    Only an "column already exists" error is benign. Every other failure used
    to be swallowed by a bare `except Exception: pass`, so a genuinely broken
    migration looked identical to a no-op and the app booted against a schema
    missing the usage columns — which then 500s on every limit check.

    Columns are checked with the inspector before each ALTER rather than by
    catching the duplicate-column error, because on PostgreSQL any failed
    statement aborts the whole enclosing transaction — and this now runs
    inside the single locked transaction schema_migrations uses to adopt a
    pre-Alembic database. Pass `conn` to run on that connection.
    """
    if conn is not None:
        _add_missing_user_columns(conn)
        return
    try:
        with engine.begin() as own_conn:
            _add_missing_user_columns(own_conn)
    except Exception:
        logger.error("User usage column migration failed", exc_info=True)
        raise
