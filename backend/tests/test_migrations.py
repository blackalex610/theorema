"""Tests for the schema-migration path.

`ensure_user_usage_columns` used to wrap every ALTER in a bare
`except Exception: pass`, so a permissions error, a locked database or a typo
looked exactly like "the column is already there" and the app booted against a
schema that 500s on every limit check. Only the duplicate-column case is
benign; everything else has to surface.
"""
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from app.database import _is_duplicate_column_error, ensure_user_usage_columns

BACKEND_ROOT = Path(__file__).resolve().parents[1]


# ─── What counts as benign ───────────────────────────────────────────────────

@pytest.mark.parametrize("message", [
    "duplicate column name: ai_theory_today",          # SQLite
    'column "ai_theory_today" of relation "users" already exists',  # PostgreSQL
    "Duplicate column name 'ai_theory_today'",         # MySQL
    "DUPLICATE COLUMN NAME: AI_THEORY_TODAY",          # case must not matter
])
def test_duplicate_column_errors_are_recognised(message):
    assert _is_duplicate_column_error(Exception(message)) is True


@pytest.mark.parametrize("message", [
    "attempt to write a readonly database",
    "database is locked",
    "permission denied for table users",
    "no such table: users",
    "connection refused",
])
def test_real_failures_are_not_mistaken_for_a_no_op(message):
    assert _is_duplicate_column_error(Exception(message)) is False


def test_the_orig_attribute_is_inspected_too():
    """SQLAlchemy wraps the driver error; the marker lives on `.orig`."""
    wrapped = OperationalError("ALTER TABLE ...", {}, Exception("duplicate column name: x"))
    assert _is_duplicate_column_error(wrapped) is True


# ─── End-to-end behaviour ────────────────────────────────────────────────────

def test_running_the_migration_twice_is_a_no_op():
    """Idempotence is the whole reason the duplicate case is swallowed."""
    ensure_user_usage_columns()
    ensure_user_usage_columns()


def test_a_genuine_failure_propagates(monkeypatch):
    """The regression that mattered: a broken migration must not boot silently."""
    import app.database as database

    class _Boom:
        def begin(self):
            raise OperationalError("ALTER TABLE ...", {}, Exception("attempt to write a readonly database"))

    monkeypatch.setattr(database, "engine", _Boom())

    with pytest.raises(OperationalError):
        ensure_user_usage_columns()


def test_a_genuine_failure_is_logged_before_it_is_raised(monkeypatch, caplog):
    import app.database as database

    class _Boom:
        def begin(self):
            raise OperationalError("ALTER TABLE ...", {}, Exception("permission denied"))

    monkeypatch.setattr(database, "engine", _Boom())

    with caplog.at_level("ERROR"), pytest.raises(OperationalError):
        ensure_user_usage_columns()

    assert any("migration failed" in record.message.lower() for record in caplog.records)


# ─── Alembic drift guard ─────────────────────────────────────────────────────

def test_alembic_env_imports_every_model_module():
    """A model module missing from env.py is invisible to --autogenerate.

    Autogenerate diffs `Base.metadata` against the live database. Any model
    module env.py forgets to import is simply absent from the metadata, so
    Alembic would happily generate a migration that DROPS its tables.
    """
    env_source = (BACKEND_ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
    model_modules = {
        path.stem
        for path in (BACKEND_ROOT / "app" / "models").glob("*.py")
        if path.stem != "__init__"
    }

    missing = {
        name for name in model_modules
        if f"import app.models.{name}" not in env_source
    }
    assert not missing, f"alembic/env.py does not import: {sorted(missing)}"


def test_a_baseline_revision_exists():
    """Without a revision, the Alembic setup tracks nothing at all."""
    versions = list((BACKEND_ROOT / "alembic" / "versions").glob("*.py"))
    assert versions, "alembic/versions is empty — schema drift is untracked"
