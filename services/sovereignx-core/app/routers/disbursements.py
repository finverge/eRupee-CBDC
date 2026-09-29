"""FSD Section 3.3 — Disbursement Orchestration Agent. Builds an
issuance instruction per eligible+consented beneficiary and submits each
to the ledger simulator via app/services/ledger_client.py (HLD 4.3's e₹
Connector Adapter contract). Runs synchronously in the request for this
scale (a production version would enqueue and process async — FSD FR-11's
retry-with-backoff — but the outcome contract to callers is identical)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Scheme, Beneficiary, DisbursementBatch, IssuanceInstruction, User, UserRole,
    EligibilityStatus, ConsentStatus, BatchStatus, InstructionStatus,
)
from app.schemas import DisbursementBatchCreate, DisbursementBatchOut, IssuanceInstructionOut
from app.security import get_current_user, require_roles
from app.services import ledger_client

router = APIRouter(prefix="/disbursements", tags=["disbursements"])


@router.post("", response_model=DisbursementBatchOut, status_code=201,
             dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.PLATFORM_ADMIN))])
def create_batch(payload: DisbursementBatchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scheme = db.query(Scheme).filter(Scheme.id == payload.scheme_id).first()
    if not scheme:
        raise HTTPException(404, "Scheme not found")
    if scheme.status.value != "active":
        raise HTTPException(400, f"Scheme is '{scheme.status.value}' — must be 'active' to disburse")

    query = db.query(Beneficiary).filter(
        Beneficiary.scheme_id == scheme.id,
        Beneficiary.eligibility_status == EligibilityStatus.ELIGIBLE,
        Beneficiary.consent_status == ConsentStatus.GRANTED,
    )
    if payload.district:
        query = query.filter(Beneficiary.district == payload.district)
    eligible_beneficiaries = query.all()

    batch = DisbursementBatch(
        scheme_id=scheme.id, district=payload.district, status=BatchStatus.PROCESSING,
        beneficiary_count=len(eligible_beneficiaries), triggered_by=user.full_name,
    )
    db.add(batch)
    db.flush()

    expires_at = scheme.validity_end.isoformat()
    confirmed, failed, total_paisa = 0, 0, 0

    for beneficiary in eligible_beneficiaries:
        external_id = f"INSTR-{uuid.uuid4()}"
        instruction = IssuanceInstruction(
            external_instruction_id=external_id, batch_id=batch.id, beneficiary_id=beneficiary.id,
            beneficiary_ref=beneficiary.beneficiary_ref, amount_paisa=scheme.benefit_amount_paisa,
        )
        db.add(instruction)
        db.flush()

        try:
            result = ledger_client.submit_issuance(
                external_instruction_id=external_id, beneficiary_ref=beneficiary.beneficiary_ref,
                amount_paisa=scheme.benefit_amount_paisa, scheme_ref=scheme.id, expires_at=expires_at,
                merchant_categories=scheme.permitted_merchant_categories, single_use=scheme.single_use,
            )
            instruction.status = InstructionStatus.CONFIRMED if result["status"] == "confirmed" else InstructionStatus.SUBMITTED
            confirmed_at_raw = result.get("confirmed_at")
            instruction.confirmed_at = datetime.fromisoformat(confirmed_at_raw) if confirmed_at_raw else None
            confirmed += 1
            total_paisa += scheme.benefit_amount_paisa
        except Exception as e:  # noqa: BLE001 — ledger simulator unreachable/rejected; recorded, not raised (FR-11)
            instruction.status = InstructionStatus.FAILED
            instruction.failure_reason = str(e)[:500]
            failed += 1

    batch.confirmed_count = confirmed
    batch.failed_count = failed
    batch.total_amount_paisa = total_paisa
    batch.status = (
        BatchStatus.CONFIRMED if failed == 0 else
        BatchStatus.PARTIALLY_FAILED if confirmed > 0 else
        BatchStatus.FAILED
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=list[DisbursementBatchOut])
def list_batches(scheme_id: str | None = None, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    q = db.query(DisbursementBatch)
    if scheme_id:
        q = q.filter(DisbursementBatch.scheme_id == scheme_id)
    return q.order_by(DisbursementBatch.created_at.desc()).all()


@router.get("/{batch_id}/instructions", response_model=list[IssuanceInstructionOut])
def list_batch_instructions(batch_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(IssuanceInstruction).filter(IssuanceInstruction.batch_id == batch_id).all()
