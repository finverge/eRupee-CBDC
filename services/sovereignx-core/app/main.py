"""
Finverge SovereignX Core — Subsidy & DBT Orchestration Engine, Retail
Banking orchestration (merchant/redemption side), compliance and consent
modules. Release 1 (BRD/FSD/HLD v1.2).

This service never custodies e₹ and never talks to RBI or a real bank
directly — see app/services/ledger_client.py and
erupee-ledger-simulator/app/config.py for the (simulated) boundary that
enforces that.

Run locally:
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8402

Then: http://localhost:8402/docs

Requires erupee-ledger-simulator running on port 8401 for disbursement
and reconciliation endpoints to work.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.routers import auth, schemes, beneficiaries, disbursements, reconciliation, dashboard, agents
from app.routers.reconciliation import run_reconciliation_cycle
from app.models import User, UserRole
from app.security import hash_password
from app.config import settings

logger = logging.getLogger("sovereignx.main")


def seed_demo_users(db) -> None:
    """One login per role so the console can be exercised end-to-end
    without a separate user-provisioning step. Change these passwords
    before any non-local deployment — see README."""
    demo_users = [
        ("admin@sovereignx.dev", "ChangeMe123!", UserRole.PLATFORM_ADMIN, "Platform Administrator"),
        ("scheme.admin@sovereignx.dev", "ChangeMe123!", UserRole.SCHEME_ADMINISTRATOR, "Scheme Administrator"),
        ("compliance@sovereignx.dev", "ChangeMe123!", UserRole.COMPLIANCE_OFFICER, "Compliance Officer"),
        ("bank.ops@sovereignx.dev", "ChangeMe123!", UserRole.SPONSOR_BANK_OPERATOR, "Sponsor Bank Operator"),
    ]
    for email, password, role, name in demo_users:
        if db.query(User).filter(User.email == email).first() is None:
            db.add(User(email=email, password_hash=hash_password(password), role=role, full_name=name))
    db.commit()


async def _reconciliation_loop():
    """Unattended reconciliation — the "no scheduled trigger" gap this
    closes. Same dev-grade in-process-loop pattern as Mandate360's
    nach-tenant-admin/app/main.py's _regulatory_watch_loop (ported at the
    user's own request there; same shape here). The interval
    (settings.reconciliation_loop_interval_seconds, default 120s) is
    deliberately short for a LOCAL DEMO so a run is observable within a
    couple of minutes of starting the service — FSD FR-31 describes a
    daily cycle, not a 2-minute one; a real deployment points this at
    whatever cadence its ops team actually wants (or drops this loop
    entirely and points an external cron at POST /reconciliation/run,
    exactly as nach-tenant-admin's own docstring describes for its
    regulatory-watch loop). One failed iteration is logged and does not
    stop the loop — a transient ledger-simulator outage shouldn't
    permanently end reconciliation for the process lifetime."""
    while True:
        await asyncio.sleep(settings.reconciliation_loop_interval_seconds)
        db = SessionLocal()
        try:
            result = await asyncio.to_thread(run_reconciliation_cycle, db)
            if result.pulled or result.agent_summaries_pulled:
                logger.info(
                    "Reconciliation loop: pulled=%d matched=%d blocked=%d new_alerts=%d agent_summaries_pulled=%d",
                    result.pulled, result.matched, result.blocked, result.new_alerts, result.agent_summaries_pulled,
                )
        except Exception:
            logger.exception("Reconciliation loop iteration failed; will retry on the next tick.")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_users(db)
    finally:
        db.close()
    loop_task = asyncio.create_task(_reconciliation_loop())
    try:
        yield
    finally:
        loop_task.cancel()


app = FastAPI(
    title=settings.app_name,
    description="Finverge SovereignX — Government & Subsidy Orchestration + Retail Banking (Release 1)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-grade, single-console local setup — tighten before any shared deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(schemes.router)
app.include_router(beneficiaries.router)
app.include_router(disbursements.router)
app.include_router(reconciliation.router)
app.include_router(dashboard.router)
app.include_router(agents.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}
