"""Bring the database to Alembic head — the only path that changes the schema.

Production used to build its schema with `Base.metadata.create_all()` from a
request middleware. create_all only ever creates *missing tables*: it never
adds a column, changes a type or drops a NOT NULL, and it writes no
`alembic_version` row. So the first model change that touched an existing
table would have silently left production behind the code — and a later
`alembic upgrade head` against that database would fail trying to create
tables create_all had already made.

`run_migrations()` replaces it:

* a database with an `alembic_version` row is upgraded to head;
* an empty database is migrated from the beginning;
* a database that has the app's tables but no `alembic_version` was built by
  the old create_all path. It is brought up to the schema as of
  LEGACY_ADOPTION_REVISION (the head when create_all was retired), stamped
  there, and then upgraded normally — so a revision added after this one
  still runs against it.

Everything happens in one transaction. On PostgreSQL that transaction first
takes an advisory lock, so serverless instances cold-starting together queue
behind one migration instead of racing it; DDL is transactional there, so a
migration that fails midway leaves nothing half-applied.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"

# Chain head when runtime create_all() was retired. A pre-Alembic database
# matches this revision once _adopt_legacy_schema has run. Never change it:
# revisions added later must still run against an adopted database.
LEGACY_ADOPTION_REVISION = "b8c9d0e1f2a3"

# The tables that exist at LEGACY_ADOPTION_REVISION. Deliberately a fixed
# list rather than "everything in Base.metadata": adoption must not create a
# table a *later* revision is responsible for, or that revision would then
# fail with "table already exists".
LEGACY_TABLES = (
    "classroom_members", "classrooms", "companion_devices", "companion_sessions",
    "event_logs", "exercise_attempts", "exercises", "generated_exams",
    "generated_lesson_content", "grades", "lesson_progress", "lessons",
    "mobile_task_contexts", "mobile_upload_records", "nvo_attempts",
    "nvo_generation_jobs", "nvo_generation_runs", "nvo_problem_embeddings",
    "nvo_problem_skills", "nvo_problems", "nvo_skills", "nvo_source_exams",
    "nvo_topics", "topics", "user_badges", "user_daily_missions",
    "user_mission_exercises", "user_progress", "user_xp_profiles", "users",
    "xp_events",
)

# Arbitrary but fixed: every instance must contend for the same lock.
_ADVISORY_LOCK_KEY = 5_318_476_721


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # alembic.ini says `script_location = alembic`, relative to the working
    # directory. A serverless function does not start in backend/, so pin it.
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    if connection is not None:
        # alembic/env.py runs on this connection (inside our transaction and
        # lock) instead of opening its own engine.
        cfg.attributes["connection"] = connection
    return cfg


def head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if head is None:
        raise RuntimeError("alembic/versions has no head revision")
    return head


def current_revision(conn: Connection) -> str | None:
    return MigrationContext.configure(conn).get_current_revision()


def _register_models() -> None:
    """Import every model module so Base.metadata knows every table.

    Globbed rather than listed, so a new model module can't be forgotten here
    the way one could be forgotten in alembic/env.py.
    """
    for path in sorted((BACKEND_ROOT / "app" / "models").glob("*.py")):
        if path.stem != "__init__":
            importlib.import_module(f"app.models.{path.stem}")


def _adopt_legacy_schema(conn: Connection) -> None:
    """Make a create_all-built database match LEGACY_ADOPTION_REVISION exactly."""
    from app.database import Base, ensure_user_usage_columns

    _register_models()
    logger.warning(
        "Database has application tables but no alembic_version — adopting a "
        "pre-Alembic schema and stamping it at %s", LEGACY_ADOPTION_REVISION,
    )

    tables = [Base.metadata.tables[name] for name in LEGACY_TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=conn, tables=tables)
    ensure_user_usage_columns(conn)

    # What the guest-users revision did beyond adding columns. SQLite cannot
    # relax a NOT NULL in place; a local dev file that old should just be
    # deleted and rebuilt, as the note in database.py already says.
    if conn.dialect.name == "postgresql":
        conn.execute(text("ALTER TABLE users ALTER COLUMN google_sub DROP NOT NULL"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
    existing_indexes = {index["name"] for index in inspect(conn).get_indexes("users")}
    if "ix_users_guest_ip_created" not in existing_indexes:
        conn.execute(text(
            "CREATE INDEX ix_users_guest_ip_created ON users (is_guest, last_login_ip, created_at)"
        ))

    command.stamp(alembic_config(conn), LEGACY_ADOPTION_REVISION)


def run_migrations(engine: Engine | None = None) -> str:
    """Upgrade the database to head. Returns the revision it ends on."""
    if engine is None:
        from app.database import engine as app_engine
        engine = app_engine

    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})

        before = current_revision(conn)
        if before is None and inspect(conn).has_table("users"):
            _adopt_legacy_schema(conn)

        command.upgrade(alembic_config(conn), "head")
        after = current_revision(conn)

    if after != before:
        logger.info("Database migrated: %s -> %s", before or "<empty>", after)
    return after or ""
