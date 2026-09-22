"""Shared pytest fixtures.

Points the app at a throwaway SQLite database before any app import so tests
never touch the real ``accounting.db``.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.TemporaryDirectory()
os.environ["ACCOUNTING_DB_PATH"] = str(Path(_TMP.name) / "test.db")

from app.database import Base, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"


@pytest.fixture(scope="session", autouse=True)
def _dispose_engine():
    yield
    engine.dispose()


@pytest.fixture()
def app_client():
    """Unauthenticated TestClient against a fresh database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app_client):
    """Authenticated TestClient (default admin user, session cookie set)."""
    response = app_client.post(
        "/api/auth/setup",
        json={"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 201
    return app_client
