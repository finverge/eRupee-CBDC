"""JWT auth (app/security.py) and role gating (require_roles)."""
from app.models import User, UserRole
from app.security import hash_password


def _make_user(db, email="admin@test.dev", password="TestPass123!", role=UserRole.PLATFORM_ADMIN):
    user = User(email=email, password_hash=hash_password(password), role=role, full_name="Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_with_correct_credentials_returns_a_token(client, db_session):
    _make_user(db_session, email="admin@test.dev", password="Correct123!")
    resp = client.post("/auth/login", json={"email": "admin@test.dev", "password": "Correct123!"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_with_wrong_password_is_401(client, db_session):
    _make_user(db_session, email="admin@test.dev", password="Correct123!")
    resp = client.post("/auth/login", json={"email": "admin@test.dev", "password": "WrongPassword"})
    assert resp.status_code == 401


def test_login_with_unknown_email_is_401(client, db_session):
    resp = client.post("/auth/login", json={"email": "nobody@test.dev", "password": "anything"})
    assert resp.status_code == 401


def test_me_endpoint_requires_a_token(client, db_session):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_endpoint_returns_current_user(client, db_session, make_user):
    user, headers = make_user(UserRole.SCHEME_ADMINISTRATOR, email="scheme@test.dev")
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "scheme@test.dev"


def test_bogus_bearer_token_is_401(client, db_session):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_role_gated_endpoint_rejects_wrong_role(client, db_session, make_user):
    """POST /reconciliation/run requires SCHEME_ADMINISTRATOR, COMPLIANCE_OFFICER,
    or PLATFORM_ADMIN — a SPONSOR_BANK_OPERATOR must not be able to trigger it."""
    _, headers = make_user(UserRole.SPONSOR_BANK_OPERATOR)
    resp = client.post("/reconciliation/run", headers=headers)
    assert resp.status_code == 403


def test_role_gated_endpoint_allows_correct_role(client, db_session, make_user, monkeypatch):
    from app.services import ledger_client
    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [])
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [])

    _, headers = make_user(UserRole.COMPLIANCE_OFFICER)
    resp = client.post("/reconciliation/run", headers=headers)
    assert resp.status_code == 200
