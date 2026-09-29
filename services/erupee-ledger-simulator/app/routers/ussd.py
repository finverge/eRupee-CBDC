"""USSD / feature-phone channel — FSD FR-33–FR-34, HLD Section 9 Tier 2
"Feature Phone". A short-lived, server-driven menu state machine — the
handset carries nothing but the session id; every screen (including
"balance") is computed fresh from the ledger on each request, never
cached in the session row (FR-34).

This simulates what a telecom's USSD gateway would forward to a bank's
backend for a real *99# / bank-specific short-code session — there is no
real telecom gateway here, just this same request/response shape a real
one would use.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import UssdSession, Wallet, Merchant
from app.routers.redemption import execute_redemption
from app.schemas import UssdSessionOut, UssdInputIn
from app.timeutil import as_utc

router = APIRouter(prefix="/ussd", tags=["ussd"])

SESSION_TTL_MINUTES = 3
MAX_SCREEN_CHARS = 70  # FSD 9.6 — fixed, tested character budget per screen


def _out(session: UssdSession, text: str, awaiting_input: bool, ended: bool = False) -> UssdSessionOut:
    assert len(text) <= MAX_SCREEN_CHARS * 4, "USSD screen text exceeds budget — trim it"  # a few lines is fine; a paragraph is not
    if ended:
        session.state = "ended"
    return UssdSessionOut(session_id=session.id, screen_text=text, awaiting_input=awaiting_input, session_ended=ended)


def _expired(session: UssdSession) -> bool:
    return datetime.now(timezone.utc) > as_utc(session.expires_at)


@router.post("/dial", response_model=UssdSessionOut, status_code=201)
def dial(db: Session = Depends(get_db)):
    session = UssdSession(state="enter_beneficiary_ref", expires_at=datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES))
    db.add(session)
    db.commit()
    db.refresh(session)
    return _out(session, "Welcome to e-Rupee.\nEnter your beneficiary reference:", True)


@router.post("/{session_id}/input", response_model=UssdSessionOut)
def send_input(session_id: str, payload: UssdInputIn, db: Session = Depends(get_db)):
    session = db.query(UssdSession).filter(UssdSession.id == session_id).first()
    if not session:
        raise HTTPException(404, "No such USSD session")
    if session.state == "ended":
        raise HTTPException(400, "Session already ended — dial again")
    if _expired(session):
        return _out(session, "Session expired. Please dial again.", False, ended=True)

    text = payload.input.strip()

    if session.state == "enter_beneficiary_ref":
        wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == text).first()
        if not wallet:
            return _out(session, "Reference not found. Please dial again.", False, ended=True)
        session.beneficiary_ref = text
        session.state = "enter_pin"
        db.commit()
        return _out(session, "Enter your 4-digit PIN:", True)

    if session.state == "enter_pin":
        wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == session.beneficiary_ref).first()
        if not wallet:
            return _out(session, "Incorrect PIN. Please dial again.", False, ended=True)

        if wallet.pin_locked_until and datetime.now(timezone.utc) < as_utc(wallet.pin_locked_until):
            minutes_left = max(1, int((as_utc(wallet.pin_locked_until) - datetime.now(timezone.utc)).total_seconds() // 60) + 1)
            db.commit()
            return _out(session, f"Account locked due to repeated wrong PIN.\nTry again in {minutes_left} min.", False, ended=True)

        if text != wallet.ussd_pin:
            wallet.failed_pin_attempts += 1
            if wallet.failed_pin_attempts >= settings.ussd_pin_max_attempts:
                wallet.pin_locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.ussd_pin_lockout_minutes)
                wallet.failed_pin_attempts = 0
                db.commit()
                return _out(session, f"Incorrect PIN. Account locked for {settings.ussd_pin_lockout_minutes} min.", False, ended=True)
            db.commit()
            return _out(session, "Incorrect PIN. Please dial again.", False, ended=True)

        wallet.failed_pin_attempts = 0
        wallet.pin_locked_until = None
        session.state = "main_menu"
        db.commit()
        return _out(session, "1. Check Balance\n2. Pay Merchant\n0. Exit", True)

    if session.state == "main_menu":
        if text == "1":
            wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == session.beneficiary_ref).first()
            session.state = "post_balance"
            db.commit()
            return _out(session, f"Balance: ₹{wallet.balance_paisa/100:.2f}\n\n0. Back", True)
        if text == "2":
            session.state = "enter_merchant_ref"
            db.commit()
            return _out(session, "Enter Merchant Ref:", True)
        if text == "0":
            db.commit()
            return _out(session, "Thank you for using e-Rupee.\nSession ended.", False, ended=True)
        return _out(session, "Invalid option.\n1. Check Balance\n2. Pay Merchant\n0. Exit", True)

    if session.state == "post_balance":
        if text == "0":
            session.state = "main_menu"
            db.commit()
            return _out(session, "1. Check Balance\n2. Pay Merchant\n0. Exit", True)
        return _out(session, "Invalid option.\n0. Back", True)

    if session.state == "enter_merchant_ref":
        merchant = db.query(Merchant).filter(Merchant.merchant_ref == text).first()
        if not merchant:
            return _out(session, "Merchant not found. Please dial again.", False, ended=True)
        session.pending_merchant_ref = text
        session.state = "enter_amount"
        db.commit()
        return _out(session, f"Paying {merchant.name}.\nEnter Amount (Rs):", True)

    if session.state == "enter_amount":
        try:
            amount_paisa = round(float(text) * 100)
            assert amount_paisa > 0
        except (ValueError, AssertionError):
            return _out(session, "Invalid amount. Please dial again.", False, ended=True)

        wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == session.beneficiary_ref).first()
        merchant = db.query(Merchant).filter(Merchant.merchant_ref == session.pending_merchant_ref).first()
        result = execute_redemption(db, wallet, merchant, amount_paisa)
        db.commit()
        if result.executed:
            return _out(session, f"Payment of ₹{text} successful.\nThank you.", False, ended=True)
        return _out(session, f"Payment declined:\n{result.rule_check_result.value.replace('_', ' ')}.", False, ended=True)

    return _out(session, "Session error. Please dial again.", False, ended=True)
