"""Agent authentication (app/security.py's require_agent_session,
app/routers/agents.py's login) and the beneficiary-side OTP dual-factor —
this is the exact area that had "no auth of its own" until this session,
so these tests lock in the fix rather than just the happy path."""
from app.models import Wallet, AgentProfile, Merchant
from app.security import hash_password


def _make_agent(db, agent_ref="AGT-TEST-001", password="TestPass123!", daily_limit_paisa=5000000):
    agent = AgentProfile(
        agent_ref=agent_ref, name="Test Agent", assigned_region="Test Region",
        daily_limit_paisa=daily_limit_paisa, password_hash=hash_password(password),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_wallet(db, beneficiary_ref="BEN-TEST-001", balance_paisa=100000):
    wallet = Wallet(beneficiary_ref=beneficiary_ref, balance_paisa=balance_paisa)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def _make_merchant(db, merchant_ref="MER-TEST-001", category="GROCERY"):
    merchant = Merchant(merchant_ref=merchant_ref, name="Test Merchant", category=category)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


def test_login_with_correct_password_succeeds(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    resp = client.post("/agents/AGT-001/login", json={"password": "Correct123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_ref"] == "AGT-001"
    assert body["token"]


def test_login_with_wrong_password_is_401(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    resp = client.post("/agents/AGT-001/login", json={"password": "WrongPassword"})
    assert resp.status_code == 401


def test_login_with_unknown_agent_is_401(client, db_session):
    resp = client.post("/agents/AGT-DOES-NOT-EXIST/login", json={"password": "anything"})
    assert resp.status_code == 401


def test_lookup_without_token_is_401(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001")
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    resp = client.get("/agents/AGT-001/lookup/BEN-001")
    assert resp.status_code == 401


def test_lookup_with_valid_token_succeeds(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=42000)
    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]

    resp = client.get("/agents/AGT-001/lookup/BEN-001", headers={"X-Agent-Token": token})
    assert resp.status_code == 200
    assert resp.json()["balance_paisa"] == 42000


def test_token_does_not_work_for_a_different_agent(client, db_session):
    """The specific gap this closed: AGT-001's session must not grant
    access under AGT-002's URL, even though both are valid, logged-in
    agents."""
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    _make_agent(db_session, agent_ref="AGT-002", password="Correct456!")
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]

    resp = client.get("/agents/AGT-002/lookup/BEN-001", headers={"X-Agent-Token": token})
    assert resp.status_code == 403


def test_bogus_token_is_401(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001")
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    resp = client.get("/agents/AGT-001/lookup/BEN-001", headers={"X-Agent-Token": "not-a-real-token"})
    assert resp.status_code == 401


def test_otp_request_requires_agent_session(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001")
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    resp = client.post("/agents/AGT-001/otp/request", json={"beneficiary_ref": "BEN-001"})
    assert resp.status_code == 401


def test_full_otp_dual_factor_flow_then_transact(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!", daily_limit_paisa=5000000)
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=100000)
    _make_merchant(db_session, merchant_ref="MER-001", category="GROCERY")

    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]
    headers = {"X-Agent-Token": token}

    otp = client.post("/agents/AGT-001/otp/request", headers=headers, json={"beneficiary_ref": "BEN-001"})
    assert otp.status_code == 200
    challenge_id, code = otp.json()["challenge_id"], otp.json()["simulated_code"]

    verify = client.post("/agents/AGT-001/otp/verify", headers=headers, json={"challenge_id": challenge_id, "code": code})
    assert verify.status_code == 200
    assert verify.json()["verified"] is True
    session_token = verify.json()["assisted_session_token"]

    txn = client.post("/agents/AGT-001/assisted/transact", headers=headers, json={
        "beneficiary_ref": "BEN-001", "action": "redemption", "amount_paisa": 5000,
        "merchant_ref": "MER-001", "assisted_session_token": session_token,
    })
    assert txn.status_code == 200
    assert txn.json()["executed"] is True


def test_otp_verify_with_wrong_code_fails(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]
    headers = {"X-Agent-Token": token}

    otp = client.post("/agents/AGT-001/otp/request", headers=headers, json={"beneficiary_ref": "BEN-001"})
    challenge_id = otp.json()["challenge_id"]

    resp = client.post("/agents/AGT-001/otp/verify", headers=headers, json={"challenge_id": challenge_id, "code": "000000"})
    assert resp.json()["verified"] is False


def test_transact_without_verified_otp_is_rejected(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!")
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=100000)
    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]

    resp = client.post("/agents/AGT-001/assisted/transact", headers={"X-Agent-Token": token}, json={
        "beneficiary_ref": "BEN-001", "action": "withdrawal", "amount_paisa": 5000,
        "assisted_session_token": "forged-token",
    })
    assert resp.status_code == 401


def test_transact_over_daily_limit_is_rejected(client, db_session):
    _make_agent(db_session, agent_ref="AGT-001", password="Correct123!", daily_limit_paisa=1000)
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=100000)
    token = client.post("/agents/AGT-001/login", json={"password": "Correct123!"}).json()["token"]
    headers = {"X-Agent-Token": token}

    otp = client.post("/agents/AGT-001/otp/request", headers=headers, json={"beneficiary_ref": "BEN-001"})
    code = otp.json()["simulated_code"]
    verify = client.post("/agents/AGT-001/otp/verify", headers=headers, json={"challenge_id": otp.json()["challenge_id"], "code": code})
    session_token = verify.json()["assisted_session_token"]

    resp = client.post("/agents/AGT-001/assisted/transact", headers=headers, json={
        "beneficiary_ref": "BEN-001", "action": "withdrawal", "amount_paisa": 5000,
        "assisted_session_token": session_token,
    })
    assert resp.status_code == 400
    assert "daily limit" in resp.json()["detail"].lower()
