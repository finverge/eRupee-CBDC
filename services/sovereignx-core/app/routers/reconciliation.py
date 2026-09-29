"""FSD Section 5 (Reconciliation Agent) + Section 4 (Fraud360/AML360 rule
pack). POST /reconciliation/run does two independent pulls in one cycle:
(1) unreconciled redemption events from the ledger simulator, matched to
the instruction that funded each one, compliance-evaluated, and acked
(HLD Figure 2, steps 8-9); (2) every onboarded agent's daily activity
summary, persisted as one row per (agent_ref, date) — FSD FR-31's
"reconciled against the sponsor bank's settlement to that agent on a
daily cycle." The two pulls share nothing but the trigger; an agent
having zero transactions today doesn't block or skip the redemption
pull, and vice versa."""
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import IssuanceInstruction, ReconciliationRecord, ComplianceAlert, AgentDailyReconciliation, User, UserRole, AlertStatus
from app.schemas import (
    ReconciliationRecordOut, ComplianceAlertOut, AlertReviewAction, ReconciliationRunResult,
    AgentDailyReconciliationOut,
)
from app.security import get_current_user, require_roles
from app.services import ledger_client, compliance

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def _pull_agent_daily_summaries(db: Session) -> int:
    try:
        agents = ledger_client.list_agents()
    except httpx.HTTPError:
        return 0  # ledger simulator unreachable — the redemption pull already surfaces that; don't fail the whole run twice

    pulled = 0
    for agent in agents:
        try:
            summary = ledger_client.get_agent_daily_summary(agent["agent_ref"])
        except httpx.HTTPError:
            continue

        existing = db.query(AgentDailyReconciliation).filter(
            AgentDailyReconciliation.agent_ref == summary["agent_ref"],
            AgentDailyReconciliation.date == summary["date"],
        ).first()
        if existing:
            existing.transaction_count = summary["transaction_count"]
            existing.total_amount_paisa = summary["total_amount_paisa"]
            existing.daily_limit_paisa = summary["daily_limit_paisa"]
            existing.pulled_at = datetime.now(timezone.utc)
        else:
            db.add(AgentDailyReconciliation(
                agent_ref=summary["agent_ref"], date=summary["date"],
                transaction_count=summary["transaction_count"], total_amount_paisa=summary["total_amount_paisa"],
                daily_limit_paisa=summary["daily_limit_paisa"],
            ))
        pulled += 1
    return pulled


def run_reconciliation_cycle(db: Session) -> ReconciliationRunResult:
    """The actual reconciliation logic, independent of FastAPI request
    context — called both by POST /run (an admin clicking the button) and
    by main.py's background loop (an unattended timer). Keeping this as a
    plain function callable from either place means the two triggers can
    never drift apart into two different implementations of "what
    reconciliation does.\""""
    events = ledger_client.pull_unreconciled_redemptions()
    matched, blocked, new_alerts = 0, 0, 0

    for event in events:
        # The simulator's redemption event carries ITS OWN internal
        # instruction_id, not our external_instruction_id, so we match by
        # beneficiary_ref among instructions not yet reconciled, newest
        # first (best-effort, appropriate to this simulator's single-
        # active-scheme-per-beneficiary scale).
        instruction = (
            db.query(IssuanceInstruction)
            .filter(IssuanceInstruction.beneficiary_ref == event["beneficiary_ref"])
            .outerjoin(ReconciliationRecord, ReconciliationRecord.instruction_id == IssuanceInstruction.id)
            .filter(ReconciliationRecord.id == None)  # noqa: E711
            .order_by(IssuanceInstruction.created_at.desc())
            .first()
        )
        if instruction is None:
            instruction = (
                db.query(IssuanceInstruction)
                .filter(IssuanceInstruction.beneficiary_ref == event["beneficiary_ref"])
                .order_by(IssuanceInstruction.created_at.desc())
                .first()
            )
        if instruction is None:
            ledger_client.ack_redemption(event["id"])
            continue

        record = ReconciliationRecord(
            instruction_id=instruction.id, external_redemption_id=event["id"],
            merchant_ref=event["merchant_ref"], merchant_category=event["merchant_category"],
            amount_paisa=event["amount_paisa"], rule_check_result=event["rule_check_result"],
            match_status="matched" if event["executed"] else "blocked",
        )
        db.add(record)
        if event["executed"]:
            matched += 1
        else:
            blocked += 1

        for alert in compliance.evaluate_redemption(
            db, event["beneficiary_ref"], event["rule_check_result"], event["amount_paisa"],
        ):
            db.add(alert)
            new_alerts += 1

        ledger_client.ack_redemption(event["id"])

    agent_summaries_pulled = _pull_agent_daily_summaries(db)

    db.commit()
    return ReconciliationRunResult(
        pulled=len(events), matched=matched, blocked=blocked, new_alerts=new_alerts,
        agent_summaries_pulled=agent_summaries_pulled,
    )


@router.post("/run", response_model=ReconciliationRunResult,
             dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.COMPLIANCE_OFFICER, UserRole.PLATFORM_ADMIN))])
def run_reconciliation(db: Session = Depends(get_db)):
    """Admin-triggered run — same cycle the background loop runs
    unattended (see main.py's _reconciliation_loop). Both exist on
    purpose: the loop keeps the system current without anyone watching
    it, this button lets a compliance officer force an immediate pull
    right after fixing something, without waiting for the next tick."""
    return run_reconciliation_cycle(db)


@router.get("/records", response_model=list[ReconciliationRecordOut])
def list_records(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(ReconciliationRecord).order_by(ReconciliationRecord.created_at.desc()).limit(200).all()


@router.get("/agent-summaries", response_model=list[AgentDailyReconciliationOut])
def list_agent_summaries(agent_ref: str | None = None, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    """History of what /reconciliation/run has pulled for each agent, one
    row per day — this is the persisted record FSD FR-31 asks for, as
    opposed to Agents.tsx's live on-demand GET .../daily-summary."""
    q = db.query(AgentDailyReconciliation)
    if agent_ref:
        q = q.filter(AgentDailyReconciliation.agent_ref == agent_ref)
    return q.order_by(AgentDailyReconciliation.date.desc(), AgentDailyReconciliation.agent_ref).limit(200).all()


@router.get("/alerts", response_model=list[ComplianceAlertOut])
def list_alerts(status: AlertStatus | None = None, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    q = db.query(ComplianceAlert)
    if status:
        q = q.filter(ComplianceAlert.status == status)
    return q.order_by(ComplianceAlert.created_at.desc()).all()


@router.post("/alerts/{alert_id}/review", response_model=ComplianceAlertOut,
             dependencies=[Depends(require_roles(UserRole.COMPLIANCE_OFFICER, UserRole.PLATFORM_ADMIN))])
def review_alert(alert_id: str, payload: AlertReviewAction, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.query(ComplianceAlert).filter(ComplianceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = AlertStatus.REVIEWED if payload.action == "review" else AlertStatus.DISMISSED
    alert.reviewed_by = user.full_name
    alert.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert
