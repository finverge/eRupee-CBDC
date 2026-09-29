"""FSD Section 3.2 (Eligibility) + 4.2 (Consent). The "Eligibility Agent"
here is a real, running check — not a black box — just a simple one
appropriate to a simulator: a beneficiary_ref already registered anywhere
in the platform is ineligible (dedup, FR-06); otherwise eligible. A
production Eligibility Agent would call out to the government source
system's own data; this one has no such system to call."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Beneficiary, Scheme, ConsentRecord, User, UserRole, EligibilityStatus, ConsentStatus
from app.schemas import BeneficiaryIngestRequest, BeneficiaryOut, ConsentAction
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/schemes/{scheme_id}/beneficiaries", tags=["beneficiaries"])


@router.post("/ingest", response_model=list[BeneficiaryOut], status_code=201,
             dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.PLATFORM_ADMIN))])
def ingest_beneficiaries(scheme_id: str, payload: BeneficiaryIngestRequest, db: Session = Depends(get_db)):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(404, "Scheme not found")

    created: list[Beneficiary] = []
    for item in payload.items:
        existing = db.query(Beneficiary).filter(Beneficiary.beneficiary_ref == item.beneficiary_ref).first()
        if existing:
            existing.eligibility_status = EligibilityStatus.INELIGIBLE
            existing.eligibility_reason = "duplicate beneficiary_ref already registered"
            created.append(existing)
            continue
        b = Beneficiary(
            scheme_id=scheme_id, beneficiary_ref=item.beneficiary_ref, full_name=item.full_name,
            district=item.district, eligibility_status=EligibilityStatus.ELIGIBLE,
            eligibility_reason="passed dedup check",
        )
        db.add(b)
        created.append(b)
    db.commit()
    for b in created:
        db.refresh(b)
    return created


@router.get("", response_model=list[BeneficiaryOut])
def list_beneficiaries(scheme_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Beneficiary).filter(Beneficiary.scheme_id == scheme_id).order_by(Beneficiary.created_at.desc()).all()


@router.post("/{beneficiary_id}/consent", response_model=BeneficiaryOut)
def record_consent(scheme_id: str, beneficiary_id: str, payload: ConsentAction,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Simulated ConsentBridge capture (FSD FR-07, FR-19) — disbursement
    is gated on this being 'granted' (see disbursements.py)."""
    beneficiary = db.query(Beneficiary).filter(Beneficiary.id == beneficiary_id, Beneficiary.scheme_id == scheme_id).first()
    if not beneficiary:
        raise HTTPException(404, "Beneficiary not found")
    if payload.action not in ("grant", "withdraw"):
        raise HTTPException(400, "action must be 'grant' or 'withdraw'")

    status_ = ConsentStatus.GRANTED if payload.action == "grant" else ConsentStatus.WITHDRAWN
    beneficiary.consent_status = status_
    db.add(ConsentRecord(beneficiary_id=beneficiary.id, status=status_, recorded_by=user.full_name))
    db.commit()
    db.refresh(beneficiary)
    return beneficiary
