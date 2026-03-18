"""Pytest fixtures for SVJ project tests.

Provides in-memory SQLite database, FastAPI TestClient, and temp dirs.
"""
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, get_db


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_engine():
    """Create a shared in-memory SQLite engine for all tests."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all models so Base knows about them
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture()
def db_session(test_engine):
    """Per-test DB session with rollback cleanup."""
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(test_engine, db_session):
    """FastAPI TestClient with DB override."""
    from fastapi.testclient import TestClient
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def tmp_upload_dir(tmp_path):
    """Temporary upload directory."""
    upload = tmp_path / "uploads"
    upload.mkdir()
    return upload
