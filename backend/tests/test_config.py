"""Tests for config resolution: secrets and the database URL must both refuse
to boot production on a placeholder value.

`_resolve_secret_key` already did this for SECRET_KEY. DATABASE_URL had no
equivalent guard: it defaults to a relative SQLite file, which Vercel silently
rewrites to /tmp (see `database._resolve_database_url`) — a missing or
misspelled env var would boot cleanly, serve traffic, and lose every user and
every progress record on the next cold start, with concurrent instances each
holding a different database. These tests pin the same fail-fast behaviour
for DATABASE_URL.
"""
import pytest

from app.config import Settings, _resolve_database_url, _resolve_secret_key


def _settings(**overrides) -> Settings:
    base = {
        "SECRET_KEY": "a" * 40,
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "ENVIRONMENT": "development",
    }
    base.update(overrides)
    return Settings(**base)


# ─── DATABASE_URL ────────────────────────────────────────────────────────────

def test_production_refuses_to_boot_with_no_database_url():
    cfg = _settings(ENVIRONMENT="production", DATABASE_URL="")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _resolve_database_url(cfg)


def test_production_refuses_to_boot_with_the_default_sqlite_file():
    cfg = _settings(ENVIRONMENT="production", DATABASE_URL="sqlite:///./mathlearning.db")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _resolve_database_url(cfg)


def test_production_accepts_a_real_database_url():
    cfg = _settings(ENVIRONMENT="production", DATABASE_URL="postgresql://u:p@host/db")
    assert _resolve_database_url(cfg) == "postgresql://u:p@host/db"


def test_development_falls_back_to_sqlite_when_unset():
    """A fresh checkout with no .env still runs — same trade-off _resolve_secret_key makes."""
    cfg = _settings(ENVIRONMENT="development", DATABASE_URL="")
    assert _resolve_database_url(cfg) == "sqlite:///./mathlearning.db"


def test_development_keeps_an_explicit_sqlite_file():
    cfg = _settings(ENVIRONMENT="development", DATABASE_URL="sqlite:///./custom.db")
    assert _resolve_database_url(cfg) == "sqlite:///./custom.db"


# ─── SECRET_KEY (existing behaviour — pinned here alongside its new sibling) ─

def test_production_still_refuses_a_placeholder_secret():
    cfg = _settings(ENVIRONMENT="production", SECRET_KEY="")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _resolve_secret_key(cfg)
