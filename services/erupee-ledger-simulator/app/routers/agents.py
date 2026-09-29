"""Agent-assisted (Banking Correspondent / CSC) channel — FSD FR-29–FR-32,
HLD Section 9 Tier 3 "No Phone". An agent alone can look up a masked
balance, but moving money requires a verified OtpChallenge: the
beneficiary-side factor of the dual-factor design (FR-30). This
simulator "sends" the OTP by returning it directly in the API response —
a real deployment routes it through the sponsor bank's own AePS/
biometric rails or an SMS gateway (see OtpChallenge's docstring)."""
import hmac
import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    AgentProfile, OtpChallenge, AssistedTransaction, Wallet, Merchant,
)
from app.routers.redemption import execute_redemption
from app.schemas import (
    AgentIn, AgentOut, OtpRequestIn, OtpRequestOut, OtpVerifyIn, OtpVerifyOut,
    AssistedBalanceOut, AssistedTransactRequest, AssistedTransactionOut, AgentDailySummaryOut,
    AgentLoginIn, AgentLoginOut,
)
from app.security import require_service_key, hash_password, verify_password, create_agent_session, require_agent_session
from app.timeutil import as_utc

router = APIRouter(prefix="/agents", tags=["agents"])

OTP_TTL_MINUTES = 5
SESSION_SECRET = settings.service_api_key  # reused as an HMAC key for assisted-session tokens — dev-grade, see module note below


def _sign_session(challenge_id: str, beneficiary_ref: str) -> str:
    """Assisted-session token = HMAC(challenge_id|beneficiary_ref), proving
    to /assisted/transact that THIS request followed a verified OTP for
    THIS beneficiary, without a separate session store. Dev-grade: a real
    deployment issues a short-lived signed token from its actual auth
    service, not an ad-hoc HMAC like this."""
    return hmac.new(SESSION_SECRET.encode(), f"{challenge_id}|{beneficiary_ref}".encode(), "sha256").hexdigest()


@router.post("", response_model=AgentOut, status_code=201, dependencies=[Depends(require_service_key)])
def onboard_agent(payload: AgentIn, db: Session = Depends(get_db)):
    if db.query(AgentProfile).filter(AgentProfile.agent_ref == payload.agent_ref).first():
        raise HTTPException(409, "Agent already onboarded")
    fields = payload.model_dump()
    password = fields.pop("password")
    agent = AgentProfile(**fields, password_hash=hash_password(password))
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/{agent_ref}/login", response_model=AgentLoginOut)
def login(agent_ref: str, payload: AgentLoginIn, db: Session = Depends(get_db)):
    """Agent App's own login — separate from the beneficiary-side OTP
    dual-factor (request_otp/verify_otp below) and from sovereignx-core's
    JWT console login. An agent must authenticate here before touching
    any beneficiary data at all."""
    agent = db.query(AgentProfile).filter(AgentProfile.agent_ref == agent_ref).first()
    if not agent or not agent.password_hash or not verify_password(payload.password, agent.password_hash):
        raise HTTPException(401, "Invalid agent reference or password")
    session = create_agent_session(db, agent)
    db.commit()
    return AgentLoginOut(agent_ref=agent.agent_ref, name=agent.name, token=session.id, expires_at=session.expires_at)


@router.get("", response_model=list[AgentOut], dependencies=[Depends(require_service_key)])
def list_agents(db: Session = Depends(get_db)):
    return db.query(AgentProfile).order_by(AgentProfile.created_at.desc()).all()


def _get_agent(agent_ref: str, db: Session) -> AgentProfile:
    agent = db.query(AgentProfile).filter(AgentProfile.agent_ref == agent_ref).first()
    if not agent:
        raise HTTPException(404, "Agent not found — onboard the agent first")
    return agent


@router.get("/{agent_ref}/lookup/{beneficiary_ref}", response_model=AssistedBalanceOut)
def lookup_balance(agent_ref: str, beneficiary_ref: str, db: Session = Depends(get_db), _agent: AgentProfile = Depends(require_agent_session)):
    """Read-only — no OTP required (FSD RBAC: agent gets masked view
    access, not transaction authority, from a lookup alone). Still
    requires the agent to be logged in (require_agent_session) — a
    lookup is beneficiary PII, not a public endpoint."""
    _get_agent(agent_ref, db)
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary")
    return AssistedBalanceOut(beneficiary_ref=beneficiary_ref, balance_paisa=wallet.balance_paisa, bank_name=settings.sponsor_bank_name)


@router.post("/{agent_ref}/otp/request", response_model=OtpRequestOut)
def request_otp(agent_ref: str, payload: OtpRequestIn, db: Session = Depends(get_db), _agent: AgentProfile = Depends(require_agent_session)):
    agent = _get_agent(agent_ref, db)
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == payload.beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary")

    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    challenge = OtpChallenge(agent_id=agent.id, beneficiary_ref=payload.beneficiary_ref, code=code, expires_at=expires_at)
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return OtpRequestOut(challenge_id=challenge.id, simulated_code=code, expires_at=expires_at)


@router.post("/{agent_ref}/otp/verify", response_model=OtpVerifyOut)
def verify_otp(agent_ref: str, payload: OtpVerifyIn, db: Session = Depends(get_db), _agent: AgentProfile = Depends(require_agent_session)):
    agent = _get_agent(agent_ref, db)
    challenge = db.query(OtpChallenge).filter(OtpChallenge.id == payload.challenge_id, OtpChallenge.agent_id == agent.id).first()
    if not challenge:
        raise HTTPException(404, "No such OTP challenge for this agent")
    if challenge.verified:
        raise HTTPException(400, "OTP already used")
    if datetime.now(timezone.utc) > as_utc(challenge.expires_at):
        raise HTTPException(400, "OTP expired — request a new one")
    if payload.code != challenge.code:
        return OtpVerifyOut(verified=False)

    challenge.verified = True
    db.commit()
    token = _sign_session(challenge.id, challenge.beneficiary_ref)
    return OtpVerifyOut(verified=True, assisted_session_token=token)


@router.post("/{agent_ref}/assisted/transact", response_model=AssistedTransactionOut)
def assisted_transact(agent_ref: str, payload: AssistedTransactRequest, db: Session = Depends(get_db), _agent: AgentProfile = Depends(require_agent_session)):
    agent = _get_agent(agent_ref, db)

    if _sign_session_lookup(db, agent.id, payload.beneficiary_ref) != payload.assisted_session_token:
        raise HTTPException(401, "Missing or invalid dual-factor confirmation — request and verify an OTP first")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_total = (
        db.query(AssistedTransaction)
        .filter(AssistedTransaction.agent_id == agent.id, AssistedTransaction.created_at >= today_start, AssistedTransaction.executed == True)  # noqa: E712
        .with_entities(AssistedTransaction.amount_paisa)
        .all()
    )
    spent_today = sum(a[0] or 0 for a in today_total)
    if spent_today + payload.amount_paisa > agent.daily_limit_paisa:
        raise HTTPException(400, f"Agent daily limit exceeded: ₹{agent.daily_limit_paisa/100:.0f}/day, ₹{spent_today/100:.0f} already used today")

    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == payload.beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary")

    if payload.action == "withdrawal":
        merchant_ref = f"CASH-{agent.agent_ref}"
        merchant = db.query(Merchant).filter(Merchant.merchant_ref == merchant_ref).first()
        if not merchant:
            merchant = Merchant(merchant_ref=merchant_ref, name=f"Cash withdrawal via {agent.name}", category="CASH_WITHDRAWAL")
            db.add(merchant)
            db.flush()
    elif payload.action == "redemption":
        if not payload.merchant_ref:
            raise HTTPException(400, "merchant_ref required for a redemption")
        merchant = db.query(Merchant).filter(Merchant.merchant_ref == payload.merchant_ref).first()
        if not merchant:
            raise HTTPException(404, "Merchant not onboarded")
    else:
        raise HTTPException(400, "action must be 'withdrawal' or 'redemption'")

    redemption = execute_redemption(db, wallet, merchant, payload.amount_paisa)

    record = AssistedTransaction(
        agent_id=agent.id, beneficiary_ref=payload.beneficiary_ref, action=payload.action,
        amount_paisa=payload.amount_paisa, merchant_ref=merchant.merchant_ref,
        auth_method="otp", rule_check_result=redemption.rule_check_result.value, executed=redemption.executed,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return AssistedTransactionOut(
        id=record.id, agent_ref=agent.agent_ref, beneficiary_ref=record.beneficiary_ref, action=record.action,
        amount_paisa=record.amount_paisa, merchant_ref=record.merchant_ref,
        rule_check_result=record.rule_check_result, executed=record.executed, created_at=record.created_at,
    )


def _sign_session_lookup(db: Session, agent_id: str, beneficiary_ref: str) -> str | None:
    """Recomputes what a valid token would be for the most recent verified,
    unexpired challenge — rather than trusting the client-supplied token
    blindly, we independently derive it server-side and compare."""
    challenge = (
        db.query(OtpChallenge)
        .filter(OtpChallenge.agent_id == agent_id, OtpChallenge.beneficiary_ref == beneficiary_ref, OtpChallenge.verified == True)  # noqa: E712
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if not challenge:
        return None
    return _sign_session(challenge.id, beneficiary_ref)


@router.get("/{agent_ref}/transactions", response_model=list[AssistedTransactionOut])
def list_transactions(agent_ref: str, db: Session = Depends(get_db)):
    agent = _get_agent(agent_ref, db)
    rows = db.query(AssistedTransaction).filter(AssistedTransaction.agent_id == agent.id).order_by(AssistedTransaction.created_at.desc()).all()
    return [
        AssistedTransactionOut(
            id=r.id, agent_ref=agent.agent_ref, beneficiary_ref=r.beneficiary_ref, action=r.action,
            amount_paisa=r.amount_paisa, merchant_ref=r.merchant_ref, rule_check_result=r.rule_check_result,
            executed=r.executed, created_at=r.created_at,
        ) for r in rows
    ]


@router.get("/{agent_ref}/daily-summary", response_model=AgentDailySummaryOut)
def daily_summary(agent_ref: str, db: Session = Depends(get_db)):
    """Pulled by sovereignx-core's reconciliation for FR-31's daily
    settlement-to-agent reconciliation (see sovereignx-core/app/routers/
    agents.py)."""
    agent = _get_agent(agent_ref, db)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(AssistedTransaction)
        .filter(AssistedTransaction.agent_id == agent.id, AssistedTransaction.created_at >= today_start, AssistedTransaction.executed == True)  # noqa: E712
        .all()
    )
    total = sum(r.amount_paisa or 0 for r in rows)
    return AgentDailySummaryOut(
        agent_ref=agent.agent_ref, date=today_start.date().isoformat(), transaction_count=len(rows),
        total_amount_paisa=total, daily_limit_paisa=agent.daily_limit_paisa, remaining_paisa=agent.daily_limit_paisa - total,
    )
