"""Test fixtures — same pattern as erupee-ledger-simulator/tests/conftest.py:
a real Postgres test database (sovereignx_core_test), one rolled-back
transaction per test, and get_db overridden so the app never touches the
real dev database. TestClient is never used as a context manager here
either — that would trigger app.main's lifespan, which seeds real demo
users AND starts the unattended _reconciliation_loop background task
against the real database."""
import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/sovereignx_core_test"


def _ensure_test_database_exists() -> None:
    conn = psycopg.connect("postgresql://postgres:postgres@localhost:5432/postgres", autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'sovereignx_core_test'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE sovereignx_core_test")
    finally:
        conn.close()


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database_exists()
    from app.database import Base
    import app.models  # noqa: F401

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
    from app.main import app
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    """Returns a factory: make_user(role, email=...) -> (User, auth_headers)."""
    from app.models import User
    from app.security import hash_password, create_access_token

    def _make(role, email=None, password="TestPass123!"):
        from app.models import UserRole
        if isinstance(role, str):
            role = UserRole(role)
        email = email or f"{role.value}@test.dev"
        user = User(email=email, password_hash=hash_password(password), role=role, full_name="Test User")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        token = create_access_token(user)
        return user, {"Authorization": f"Bearer {token}"}

    return _make
