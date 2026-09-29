"""Demo data for a fresh environment (new Postgres volume, `docker compose
up` from a clean checkout) — without this, the ledger simulator starts
completely empty and there's nothing to look up, pay, or reconcile
against. Idempotent (checked by ref before insert, same pattern as
sovereignx-core's seed_demo_users), so it's safe to run on every startup
against an already-seeded database too."""
from sqlalchemy.orm import Session

from app.models import Wallet, Merchant, AgentProfile
from app.security import hash_password

DEMO_AGENT_PASSWORD = "ChangeMe123!"  # same convention as sovereignx-core's demo console logins — change before any non-local deployment


def seed_demo_data(db: Session) -> None:
    if db.query(Wallet).filter(Wallet.beneficiary_ref == "BEN-CORE-001").first() is None:
        db.add(Wallet(beneficiary_ref="BEN-CORE-001", balance_paisa=705500, ussd_pin="1234"))

    demo_merchants = [
        ("MER-001", "Grameen Grocery & Provisions", "GROCERY"),
        ("MER-002", "Green Fields Fertilizer Depot", "FERTILIZER"),
    ]
    for merchant_ref, name, category in demo_merchants:
        if db.query(Merchant).filter(Merchant.merchant_ref == merchant_ref).first() is None:
            db.add(Merchant(merchant_ref=merchant_ref, name=name, category=category))

    demo_agents = [
        ("AGT-001", "Ravi Kumar (CSC Nashik)", "Nashik", 5000000),
        ("AGT-002", "Priya Sharma (CSC Solapur)", "Solapur", 3000000),
        ("AGT-003", "Anita Desai (CSC Pune)", "Pune", 5000000),
    ]
    for agent_ref, name, region, daily_limit_paisa in demo_agents:
        if db.query(AgentProfile).filter(AgentProfile.agent_ref == agent_ref).first() is None:
            db.add(AgentProfile(
                agent_ref=agent_ref, name=name, assigned_region=region,
                daily_limit_paisa=daily_limit_paisa, password_hash=hash_password(DEMO_AGENT_PASSWORD),
            ))

    db.commit()
