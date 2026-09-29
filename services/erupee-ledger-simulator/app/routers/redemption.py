"""Simulates a beneficiary redeeming e₹ at a merchant QR/POS and the
sponsor bank enforcing that instruction's programmable rules in real time
(HLD "the sponsor bank enforces rules... at the ledger level in real
time" — Figure 2, step 8). sovereignx-core never enforces rules itself; it
only observes the outcome via GET /redemptions (FSD FR-14).

Rule matching: a wallet's balance is an aggregate of possibly several
issuance instructions, each with its own rule set, so a redemption is
checked against the beneficiary's most recent CONFIRMED instruction whose
rules actually permit it (merchant category, expiry, single-use). This is
a simplification appropriate to a simulator with one active scheme per
beneficiary at a time — a production ledger would track rule provenance
per unit of the balance, not just per instruction. geo_fence is stored but
not enforced here: nothing in this simulator's redemption request carries
a location, so pretending to check it would be exactly the kind of fake
enforcement this codebase avoids.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Wallet, Merchant, IssuanceInstruction, InstructionStatus, RedemptionEvent, RuleCheckResult
from app.schemas import RedemptionRequest, RedemptionOut
from app.security import require_service_key

router = APIRouter(prefix="/redemptions", tags=["redemptions"], dependencies=[Depends(require_service_key)])


def _check_instruction_rules(instruction: IssuanceInstruction, merchant: Merchant, db: Session) -> RuleCheckResult:
    rules = instruction.rules or {}
    expires_at = rules.get("expires_at")
    if expires_at:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp:
            return RuleCheckResult.BLOCKED_EXPIRED

    categories = rules.get("merchant_categories")
    if categories and merchant.category not in categories:
        return RuleCheckResult.BLOCKED_MERCHANT_CATEGORY

    if rules.get("single_use"):
        already_used = db.query(RedemptionEvent).filter(
            RedemptionEvent.instruction_id == instruction.id,
            RedemptionEvent.executed == True,  # noqa: E712
        ).first()
        if already_used:
            return RuleCheckResult.BLOCKED_SINGLE_USE

    return RuleCheckResult.ALLOWED


def execute_redemption(db: Session, wallet: Wallet, merchant: Merchant, amount_paisa: int) -> RedemptionEvent:
    """Shared by both the service-to-service /redemptions endpoint (merchant
    scanning the beneficiary's QR) and public_wallet.py's beneficiary-
    initiated variant (scanning the merchant's QR from inside the wallet
    app) — one rule-enforcement path, two directions of the same tap."""
    if wallet.balance_paisa < amount_paisa:
        event = RedemptionEvent(
            wallet_id=wallet.id, beneficiary_ref=wallet.beneficiary_ref, instruction_id=None,
            merchant_ref=merchant.merchant_ref, merchant_category=merchant.category,
            amount_paisa=amount_paisa, rule_check_result=RuleCheckResult.BLOCKED_INSUFFICIENT_BALANCE,
            executed=False,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    candidates = db.query(IssuanceInstruction).filter(
        IssuanceInstruction.wallet_id == wallet.id,
        IssuanceInstruction.status == InstructionStatus.CONFIRMED,
    ).order_by(IssuanceInstruction.created_at.desc()).all()

    chosen = None
    chosen_result = RuleCheckResult.ALLOWED
    for candidate in candidates:
        result = _check_instruction_rules(candidate, merchant, db)
        if result == RuleCheckResult.ALLOWED:
            chosen = candidate
            chosen_result = result
            break
        if chosen is None:
            chosen, chosen_result = candidate, result  # keep the most recent failure reason if nothing passes

    executed = chosen_result == RuleCheckResult.ALLOWED
    if executed:
        wallet.balance_paisa -= amount_paisa
        merchant.settlement_balance_paisa += amount_paisa

    event = RedemptionEvent(
        wallet_id=wallet.id, beneficiary_ref=wallet.beneficiary_ref,
        instruction_id=chosen.id if chosen else None,
        merchant_ref=merchant.merchant_ref, merchant_category=merchant.category,
        amount_paisa=amount_paisa, rule_check_result=chosen_result, executed=executed,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("", response_model=RedemptionOut, status_code=201)
def redeem(payload: RedemptionRequest, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == payload.beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary")
    merchant = db.query(Merchant).filter(Merchant.merchant_ref == payload.merchant_ref).first()
    if not merchant:
        raise HTTPException(404, "Merchant not onboarded")
    return execute_redemption(db, wallet, merchant, payload.amount_paisa)


@router.get("", response_model=list[RedemptionOut])
def list_redemptions(since_unpulled_only: bool = Query(default=False), db: Session = Depends(get_db)):
    """sovereignx-core's Reconciliation Agent polls this (FSD FR-13) with
    since_unpulled_only=true, then calls POST /redemptions/{id}/ack."""
    q = db.query(RedemptionEvent)
    if since_unpulled_only:
        q = q.filter(RedemptionEvent.pulled_by_core == False)  # noqa: E712
    return q.order_by(RedemptionEvent.created_at.asc()).all()


@router.post("/{redemption_id}/ack", status_code=204)
def ack_redemption(redemption_id: str, db: Session = Depends(get_db)):
    event = db.query(RedemptionEvent).filter(RedemptionEvent.id == redemption_id).first()
    if not event:
        raise HTTPException(404, "No such redemption event")
    event.pulled_by_core = True
    db.commit()
