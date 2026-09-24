"""Tests for run_migrations(): Alembic, not create_all(), owns the schema.

Each test builds its own throwaway database — the shared test database is
built with create_all by conftest and deliberately left alone.

Every test runs on SQLite, and on PostgreSQL too when TEST_POSTGRES_URL points
at a server this suite may create and drop databases on (CI sets it). The
production-only paths — the advisory lock, dropping NOT NULL in place,
transactional DDL — only get exercised there.
"""
import os
import threading
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.database import Base
from app.services import schema_migrations
from app.services.schema_migrations import (
    LEGACY_ADOPTION_REVISION,
    LEGACY_TABLES,
    alembic_config,
    current_revision,
    head_revision,
    run_migrations,
)


POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")


@pytest.fixture(params=["sqlite", "postgresql"])
def dialect(request):
    if request.param == "postgresql" and not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL not set")
    return request.param


@pytest.fixture
def make_engine(tmp_path, dialect):
    engines = []
    databases = []
    admin = create_engine(POSTGRES_URL, isolation_level="AUTOCOMMIT") if dialect == "postgresql" else None

    def _make(name: str = "db"):
        if dialect == "sqlite":
            engine = create_engine(f"sqlite:///{(tmp_path / f'{name}.db').as_posix()}")
        else:
            db_name = f"migr_{uuid.uuid4().hex[:12]}"
            with admin.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            databases.append(db_name)
            engine = create_engine(make_url(POSTGRES_URL).set(database=db_name))
        engines.append(engine)
        return engine

    yield _make
    for engine in engines:
        engine.dispose()
    if admin is not None:
        with admin.connect() as conn:
            for db_name in databases:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin.dispose()


def _tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _revision(engine) -> str | None:
    with engine.connect() as conn:
        return current_revision(conn)


def _legacy_database(engine):
    """What the old runtime path produced: create_all, no alembic_version."""
    schema_migrations._register_models()
    Base.metadata.create_all(bind=engine)
    return engine


# ─── Fresh and already-migrated databases ────────────────────────────────────

def test_a_fresh_database_is_migrated_to_head(make_engine):
    engine = make_engine()
    assert run_migrations(engine) == head_revision()
    assert _revision(engine) == head_revision()
    assert set(LEGACY_TABLES) <= _tables(engine)


def test_running_twice_is_a_no_op(make_engine):
    engine = make_engine()
    run_migrations(engine)
    assert run_migrations(engine) == head_revision()


def test_migrations_run_from_any_working_directory(make_engine, tmp_path, monkeypatch):
    """alembic.ini's script_location is cwd-relative; a serverless function
    does not start in backend/."""
    monkeypatch.chdir(tmp_path)
    engine = make_engine()
    assert run_migrations(engine) == head_revision()


# ─── Databases built by the retired create_all() path ────────────────────────

def test_a_create_all_database_is_adopted_and_stamped(make_engine):
    engine = _legacy_database(make_engine())
    assert _revision(engine) is None

    assert run_migrations(engine) == head_revision()
    assert _revision(engine) == head_revision()


def test_adoption_keeps_existing_rows(make_engine):
    from sqlalchemy.orm import Session

    from app.models.user import User

    engine = _legacy_database(make_engine())
    with Session(engine) as session:
        session.add(User(google_sub="sub-1", email="kept@example.test", name="Kept"))
        session.commit()

    run_migrations(engine)

    with engine.connect() as conn:
        emails = [row[0] for row in conn.execute(text("SELECT email FROM users"))]
    assert emails == ["kept@example.test"]


def test_adoption_adds_user_columns_create_all_never_added(make_engine):
    """create_all never alters an existing table — that was the whole problem."""
    engine = _legacy_database(make_engine())
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_users_guest_ip_created"))
        conn.execute(text("ALTER TABLE users DROP COLUMN ai_theory_today"))

    run_migrations(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert "ai_theory_today" in columns
    indexes = {i["name"] for i in inspect(engine).get_indexes("users")}
    assert "ix_users_guest_ip_created" in indexes


def test_legacy_tables_match_the_adoption_revision_exactly(make_engine):
    """LEGACY_TABLES must be precisely the schema at LEGACY_ADOPTION_REVISION.

    A table missing from the list would be left uncreated on an adopted
    database; an extra one (from a later revision) would make that revision
    fail with "table already exists".
    """
    engine = make_engine()
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), LEGACY_ADOPTION_REVISION)
    assert _tables(engine) == set(LEGACY_TABLES)


def test_adoption_relaxes_the_guest_not_null_on_postgres(make_engine, dialect):
    """The guest-users revision dropped NOT NULL on google_sub/email; a
    database stamped past it must really have that change."""
    if dialect != "postgresql":
        pytest.skip("SQLite cannot relax NOT NULL in place")
    engine = _legacy_database(make_engine())
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ALTER COLUMN google_sub SET NOT NULL"))
        conn.execute(text("ALTER TABLE users ALTER COLUMN email SET NOT NULL"))

    run_migrations(engine)

    nullable = {c["name"]: c["nullable"] for c in inspect(engine).get_columns("users")}
    assert nullable["google_sub"] and nullable["email"]


def test_concurrent_cold_starts_do_not_race(make_engine, dialect):
    """Several serverless instances hit an empty database at once. Without the
    advisory lock the losers fail on CREATE TABLE or on the version row."""
    if dialect != "postgresql":
        pytest.skip("the advisory lock is PostgreSQL-only")
    engine = make_engine()
    results, errors = [], []

    def cold_start():
        try:
            results.append(run_migrations(engine))
        except Exception as exc:  # pragma: no cover - the failure being tested for
            errors.append(exc)

    threads = [threading.Thread(target=cold_start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert results == [head_revision()] * 4


# ─── The app wiring ──────────────────────────────────────────────────────────

def test_the_app_does_not_migrate_when_auto_migrate_is_off(monkeypatch):
    import app.main as main

    calls = []
    monkeypatch.setattr(main, "_schema_ready", False)
    monkeypatch.setattr(main, "run_migrations", lambda: calls.append(1) or "rev")
    monkeypatch.setattr(main.settings, "DB_AUTO_MIGRATE", False)
    main._ensure_schema()
    assert calls == []

    monkeypatch.setattr(main.settings, "DB_AUTO_MIGRATE", True)
    main._ensure_schema()
    main._ensure_schema()
    assert calls == [1], "migrates once per process, not per request"


def test_a_failed_migration_is_retried_on_the_next_request(monkeypatch):
    import app.main as main

    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("database unreachable")
        return "rev"

    monkeypatch.setattr(main, "_schema_ready", False)
    monkeypatch.setattr(main, "run_migrations", flaky)
    monkeypatch.setattr(main.settings, "DB_AUTO_MIGRATE", True)
    main._ensure_schema()
    main._ensure_schema()
    assert len(attempts) == 2
    assert main._schema_ready is True


def test_readiness_reports_a_migrated_database_as_ready(make_engine, monkeypatch):
    from app.routers import health

    engine = make_engine()
    run_migrations(engine)
    monkeypatch.setattr(health, "engine", engine)
    status, body = health._readiness()
    assert status == 200
    assert body["status"] == "ready"


def test_readiness_flags_an_unmigrated_database(make_engine, monkeypatch):
    from app.routers import health

    monkeypatch.setattr(health, "engine", _legacy_database(make_engine()))
    status, body = health._readiness()
    assert status == 503
    assert body["status"] == "schema_behind"
