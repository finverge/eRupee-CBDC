"""Outbound half of the e₹ Connector Adapter contract (HLD 4.3): SovereignX
core submits an issuance instruction, this simulator executes it against
the simulated ledger and reports status back. Simulated settlement is
synchronous (confirmed immediately) — a real sponsor bank connector would
be async with a webhook/poll for confirmation, which is exactly why
sovereignx-core's own client treats this call as fire-and-poll rather than
assuming an instant response, so it will not need to change when a real
bank connector replaces this simulator."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Wallet, IssuanceInstruction, InstructionStatus
from app.schemas import IssuanceRequest, IssuanceOut
from app.security import require_service_key

router = APIRouter(prefix="/issuance", tags=["issuance"], dependencies=[Depends(require_service_key)])


@router.post("", response_model=IssuanceOut, status_code=201)
def submit_issuance(payload: IssuanceRequest, db: Session = Depends(get_db)):
    existing = db.query(IssuanceInstruction).filter(
        IssuanceInstruction.external_instruction_id == payload.external_instruction_id
    ).first()
    if existing:
        return existing  # idempotent resubmit — same behaviour a real adapter's retry-with-backoff (FSD FR-11) needs

    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == payload.beneficiary_ref).first()
    if not wallet:
        wallet = Wallet(beneficiary_ref=payload.beneficiary_ref, balance_paisa=0)
        db.add(wallet)
        db.flush()

    instruction = IssuanceInstruction(
        external_instruction_id=payload.external_instruction_id,
        wallet_id=wallet.id,
        beneficiary_ref=payload.beneficiary_ref,
        amount_paisa=payload.amount_paisa,
        scheme_ref=payload.scheme_ref,
        rules=payload.rules.model_dump(mode="json"),
        status=InstructionStatus.CONFIRMED,
    )
    from app.models import _now
    instruction.confirmed_at = _now()
    wallet.balance_paisa += payload.amount_paisa

    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return instruction


@router.get("/{external_instruction_id}", response_model=IssuanceOut)
def get_issuance_status(external_instruction_id: str, db: Session = Depends(get_db)):
    instruction = db.query(IssuanceInstruction).filter(
        IssuanceInstruction.external_instruction_id == external_instruction_id
    ).first()
    if not instruction:
        raise HTTPException(404, "No such instruction")
    return instruction


@router.get("", response_model=list[IssuanceOut])
def list_issuances(db: Session = Depends(get_db)):
    return db.query(IssuanceInstruction).order_by(IssuanceInstruction.created_at.desc()).all()
