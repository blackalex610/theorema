from pydantic_settings import BaseSettings
from typing import List
import os
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

    # JWT Authentication — MUST be overridden via .env in any real deployment.
    # A random, non-guessable key is generated at import time when none is set,
    # so JWTs are never signed with the old public placeholder default.
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "") or secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

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


settings = Settings()
