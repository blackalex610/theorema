from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Math Learning Platform"
    ENVIRONMENT: str = "production"
    # DEBUG defaults OFF. It is only enabled when explicitly set via env, never
    # in code, so a mis-set deploy env won't leak every SQL statement.
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./mathlearning.db"
    # For PostgreSQL: "postgresql://postgres:***@localhost:5432/mathlearning"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # Allow any local network IP (192.168.x.x or 10.x.x.x) for mobile testing
    CORS_ALLOW_LOCAL_NETWORK: bool = True

    # JWT Authentication — MUST be supplied via env / .env in any real deployment.
    # Left empty by default on purpose: an empty value is the signal that no key
    # was configured, which _resolve_secret_key() turns into a hard startup
    # failure in production (and a throwaway random key in development).
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    # 7 days. A short expiry with no refresh endpoint guaranteed a mid-exam
    # logout (the NVO practice exam runs 150 minutes) and, combined with the
    # frontend's old hard-reload-on-401 handler, destroyed in-progress
    # answers. There is no token revocation today regardless of expiry length
    # — a short-lived access token defends against nothing an attacker with
    # localStorage access couldn't already do immediately — so a long expiry
    # trades an unrevokable-for-30-minutes token for an unrevokable-for-7-days
    # one, in exchange for eliminating a guaranteed data-loss bug.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Google OAuth
    GOOGLE_CLIENT_ID: str = "845529160700-gp4b283t7n83s7kj147el2qq72quu3ie.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = ""
    
    # OpenAI (for future implementation)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_NVO_MODEL: str = "gpt-4.1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Secrets that must never be used to sign real JWTs.
_INSECURE_SECRETS = {
    "",
    "your-secret-key-change-this-in-production",
    "changeme",
    "secret",
}


def _resolve_secret_key(cfg: "Settings") -> str:
    """Return the JWT signing key, refusing to boot production with a bad one.

    A placeholder key lets anyone mint valid admin tokens. A missing key used
    to fall back to a per-process random value, which silently invalidates
    every JWT on restart and differs across workers — so in production both
    are hard startup failures. Development still gets a random throwaway key
    so a fresh checkout runs without any setup.
    """
    key = (cfg.SECRET_KEY or "").strip()
    is_production = cfg.ENVIRONMENT.lower() in {"production", "prod"}

    if not is_production:
        return key or secrets.token_hex(32)

    lowered = key.lower()
    # Substring check, not just an exact-match set: "smartnvo-production-
    # secret-change-me" is 36 characters and passed the length check while
    # its own name says not to use it. Any key that still says "change me" is
    # a placeholder regardless of how long it happens to be.
    looks_like_placeholder = "change-me" in lowered or "changeme" in lowered
    if lowered in _INSECURE_SECRETS or looks_like_placeholder or len(key) < 32:
        raise RuntimeError(
            "SECRET_KEY must be set to a strong, unique value (at least 32 characters) "
            "via the environment or .env when ENVIRONMENT=production. Refusing to start "
            "rather than sign tokens with a guessable or ephemeral key."
        )
    return key


settings = Settings()
settings.SECRET_KEY = _resolve_secret_key(settings)
