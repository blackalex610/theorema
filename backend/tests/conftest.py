"""Shared pytest fixtures.

Every test runs against a throwaway SQLite file, never the configured
DATABASE_URL — these settings must be in place *before* `app.database` is
imported, since the engine is built at import time.
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

_TMP_DB = Path(tempfile.gettempdir()) / "mathlearning_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "pytest-secret-key-not-used-in-any-real-deploy"
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    import app.models.curriculum  # noqa: F401
    import app.models.progress  # noqa: F401
    import app.models.companion  # noqa: F401
    import app.models.nvo_exam  # noqa: F401
    import app.models.nvo_content  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    _TMP_DB.unlink(missing_ok=True)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def nvo_db(db):
    """Database fixture for NVO tests with proper table cleanup.

    Clears NVO tables after each test to ensure proper test isolation.
    """
    yield db
    # Clear NVO tables after test to prevent data leakage between tests
    from app.models.nvo_content import NvoProblemSkill, NvoProblem, NvoSkill, NvoTopic, NvoSourceExam
    db.query(NvoProblemSkill).delete()
    db.query(NvoProblem).delete()
    db.query(NvoSkill).delete()
    db.query(NvoTopic).delete()
    db.query(NvoSourceExam).delete()
    db.commit()


@pytest.fixture
def make_user(db):
    """Create a persisted user. Counter keeps emails unique across tests."""
    created: list[User] = []

    def _make(plan: str = "free", is_admin: int = 0, **overrides) -> User:
        suffix = f"{id(created)}-{len(created)}"
        user = User(
            google_sub=f"google-sub-{suffix}",
            email=f"user-{suffix}@example.test",
            name="Test User",
            plan=plan,
            is_admin=is_admin,
            **overrides,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created.append(user)
        return user

    yield _make

    for user in created:
        db.delete(user)
    db.commit()
