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


# ─── CORS_ORIGINS ────────────────────────────────────────────────────────────
#
# Typed as a bare List[str], pydantic-settings only accepted a JSON list from
# the environment, so `CORS_ORIGINS=https://app.example` — exactly what
# DEPLOYMENT.md tells an operator to set — raised a SettingsError at import
# and the backend never booted. These go through the real env source rather
# than Settings(**kwargs), because the crash lived in env parsing.

def _settings_from_env(monkeypatch, value: str) -> Settings:
    monkeypatch.setenv("CORS_ORIGINS", value)
    return Settings(_env_file=None)


def test_cors_origins_accepts_a_single_origin(monkeypatch):
    cfg = _settings_from_env(monkeypatch, "https://smartnvo.vercel.app")
    assert cfg.CORS_ORIGINS == ["https://smartnvo.vercel.app"]


def test_cors_origins_accepts_a_comma_separated_list(monkeypatch):
    cfg = _settings_from_env(monkeypatch, "https://a.example, https://b.example")
    assert cfg.CORS_ORIGINS == ["https://a.example", "https://b.example"]


def test_cors_origins_still_accepts_a_json_list(monkeypatch):
    cfg = _settings_from_env(monkeypatch, '["https://a.example", "https://b.example"]')
    assert cfg.CORS_ORIGINS == ["https://a.example", "https://b.example"]


def test_cors_origins_drops_trailing_slashes_and_empty_entries(monkeypatch):
    """Browsers send Origin with no trailing slash and the match is exact."""
    cfg = _settings_from_env(monkeypatch, "https://a.example/,, ")
    assert cfg.CORS_ORIGINS == ["https://a.example"]


def test_cors_origins_default_is_localhost_only(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.CORS_ORIGINS
    assert all("localhost" in o or "127.0.0.1" in o for o in cfg.CORS_ORIGINS)


def test_local_network_origins_are_allowed_in_development_only(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "CORS_ORIGINS", ["https://app.example"])
    monkeypatch.setattr(config.settings, "CORS_ALLOW_LOCAL_NETWORK", True)

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "development")
    assert config.is_allowed_origin("http://192.168.1.20:5173")
    assert config.is_allowed_origin("https://app.example")
    assert not config.is_allowed_origin("https://evil.example")

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    assert not config.is_allowed_origin("http://192.168.1.20:5173")
    assert config.is_allowed_origin("https://app.example")


def test_local_network_regex_rejects_lookalike_hosts(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "CORS_ORIGINS", [])
    monkeypatch.setattr(config.settings, "CORS_ALLOW_LOCAL_NETWORK", True)
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "development")
    assert not config.is_allowed_origin("http://192.168.1.20.evil.example")
    assert not config.is_allowed_origin("http://172.32.0.1")
