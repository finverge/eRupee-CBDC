"""app/seed.py — must be idempotent since it runs on every startup
(including against an already-seeded database)."""
from app.models import Wallet, Merchant, AgentProfile
from app.seed import seed_demo_data


def test_seed_creates_expected_demo_data(db_session):
    seed_demo_data(db_session)

    assert db_session.query(Wallet).filter(Wallet.beneficiary_ref == "BEN-CORE-001").count() == 1
    assert db_session.query(Merchant).count() == 2
    assert db_session.query(AgentProfile).count() == 3


def test_seed_is_idempotent(db_session):
    seed_demo_data(db_session)
    seed_demo_data(db_session)
    seed_demo_data(db_session)

    assert db_session.query(Wallet).filter(Wallet.beneficiary_ref == "BEN-CORE-001").count() == 1
    assert db_session.query(Merchant).count() == 2
    assert db_session.query(AgentProfile).count() == 3


def test_seeded_agents_can_log_in(client, db_session):
    from app.seed import DEMO_AGENT_PASSWORD
    seed_demo_data(db_session)

    resp = client.post("/agents/AGT-001/login", json={"password": DEMO_AGENT_PASSWORD})
    assert resp.status_code == 200
