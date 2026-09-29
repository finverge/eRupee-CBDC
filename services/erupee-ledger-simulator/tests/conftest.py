"""Test fixtures. Runs against a REAL Postgres database
(erupee_ledger_simulator_test on the same local instance the dev server
uses — see local-postgres-instance project memory), not SQLite — this
codebase has already been bitten once by a Postgres-specific bug
(app/timeutil.py's as_utc() fix) that an in-memory SQLite DB would never
have surfaced, since SQLite has no server-side session timezone at all.

Each test runs inside its own transaction that's rolled back afterward
(the standard SQLAlchemy "transactional test" pattern) — tests never see
each other's data and never touch the real dev database, because the
FastAPI app's own module-level `engine` (created from `settings.
database_url`) is never used here; `client` overrides `get_db` to hand
out sessions bound to the TEST engine instead."""
import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/erupee_ledger_simulator_test"


def _ensure_test_database_exists() -> None:
    conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/postgres", autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'erupee_ledger_simulator_test'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE erupee_ledger_simulator_test")
    finally:
        conn.close()


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database_exists()
    from app.database import Base
    import app.models  # noqa: F401 — registers every model on Base.metadata before create_all

    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """Deliberately does NOT use `with TestClient(app) as c:` — that would
    trigger the app's lifespan (Base.metadata.create_all + seed_demo_data
    against the REAL dev database from settings.database_url), which
    tests must never touch."""
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def service_key_headers():
    from app.config import settings
    return {"X-Service-Key": settings.service_api_key}
