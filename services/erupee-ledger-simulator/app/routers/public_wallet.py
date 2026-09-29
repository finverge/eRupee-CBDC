"""Public (beneficiary-facing) wallet endpoints — what the SovereignX
Wallet SDK, embedded in a sponsor bank's own app, actually calls. No
X-Service-Key here: in a real deployment the bank authenticates its own
customer (login/biometric/OTP) and this would sit behind THAT session,
not a service-to-service secret — this simulator doesn't implement
beneficiary-level auth, so these endpoints are open, which is a
deliberate simplification for local development only. Never expose this
service directly to the internet as-is.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Wallet, Merchant, IssuanceInstruction, InstructionStatus, RedemptionEvent
from app.routers.redemption import execute_redemption
from app.schemas import RedemptionRequest, RedemptionOut, WalletOut

router = APIRouter(prefix="/public/wallet", tags=["public-wallet"])


@router.get("/{beneficiary_ref}", response_model=WalletOut)
def get_balance(beneficiary_ref: str, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet found for this beneficiary yet")
    return wallet


@router.get("/{beneficiary_ref}/history")
def get_history(beneficiary_ref: str, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet found for this beneficiary yet")

    credits = db.query(IssuanceInstruction).filter(
        IssuanceInstruction.wallet_id == wallet.id, IssuanceInstruction.status == InstructionStatus.CONFIRMED,
    ).all()
    debits = db.query(RedemptionEvent).filter(RedemptionEvent.wallet_id == wallet.id, RedemptionEvent.executed == True).all()  # noqa: E712

    events = [
        {"type": "credit", "amount_paisa": c.amount_paisa, "label": "Subsidy disbursement", "at": c.confirmed_at or c.created_at}
        for c in credits
    ] + [
        {"type": "debit", "amount_paisa": d.amount_paisa, "label": f"Payment to {d.merchant_ref}", "at": d.created_at}
        for d in debits
    ]
    events.sort(key=lambda e: e["at"], reverse=True)
    return events


@router.get("/{beneficiary_ref}/permitted-categories")
def get_permitted_categories(beneficiary_ref: str, db: Session = Depends(get_db)):
    """Lets the wallet UI show the beneficiary what they can still spend on
    — reads the most recent confirmed instruction's rules, same lookup
    POST /public/wallet/{ref}/redeem itself uses."""
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet found for this beneficiary yet")
    latest = db.query(IssuanceInstruction).filter(
        IssuanceInstruction.wallet_id == wallet.id, IssuanceInstruction.status == InstructionStatus.CONFIRMED,
    ).order_by(IssuanceInstruction.created_at.desc()).first()
    if not latest:
        return {"merchant_categories": None, "expires_at": None}
    rules = latest.rules or {}
    return {"merchant_categories": rules.get("merchant_categories"), "expires_at": rules.get("expires_at")}


@router.post("/{beneficiary_ref}/redeem", response_model=RedemptionOut, status_code=201)
def redeem_from_wallet(beneficiary_ref: str, payload: RedemptionRequest, db: Session = Depends(get_db)):
    """Same rule-enforcement logic as the service-to-service /redemptions
    endpoint (merchant scanning the beneficiary's QR) — this variant is
    the beneficiary-initiated direction (scanning the MERCHANT's QR from
    inside their own wallet app), which is why beneficiary_ref comes from
    the URL/session rather than the request body."""
    if payload.beneficiary_ref != beneficiary_ref:
        raise HTTPException(400, "beneficiary_ref mismatch")

    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary")
    merchant = db.query(Merchant).filter(Merchant.merchant_ref == payload.merchant_ref).first()
    if not merchant:
        raise HTTPException(404, "Merchant not onboarded")
    return execute_redemption(db, wallet, merchant, payload.amount_paisa)
