from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Beneficiary, DisbursementBatch, ReconciliationRecord, ComplianceAlert, User,
    EligibilityStatus, AlertStatus,
)
from app.schemas import DashboardOut, FunnelOut
from app.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    beneficiaries_onboarded = db.query(Beneficiary).count()
    eligible_count = db.query(Beneficiary).filter(Beneficiary.eligibility_status == EligibilityStatus.ELIGIBLE).count()

    batches = db.query(DisbursementBatch).all()
    total_disbursed_paisa = sum(b.total_amount_paisa for b in batches)

    records = db.query(ReconciliationRecord).all()
    matched = [r for r in records if r.match_status == "matched"]
    total_redeemed_paisa = sum(r.amount_paisa for r in matched)

    open_alerts_q = db.query(ComplianceAlert).filter(ComplianceAlert.status == AlertStatus.OPEN)
    open_alerts = open_alerts_q.count()

    redemption_rate = (total_redeemed_paisa / total_disbursed_paisa * 100) if total_disbursed_paisa else 0.0

    recent_batches = db.query(DisbursementBatch).order_by(DisbursementBatch.created_at.desc()).limit(5).all()
    open_alert_list = open_alerts_q.order_by(ComplianceAlert.created_at.desc()).limit(10).all()

    return DashboardOut(
        beneficiaries_onboarded=beneficiaries_onboarded,
        total_disbursed_paisa=total_disbursed_paisa,
        total_redeemed_paisa=total_redeemed_paisa,
        redemption_rate_pct=round(redemption_rate, 1),
        open_alerts=open_alerts,
        funnel=FunnelOut(
            eligible=eligible_count,
            disbursed=sum(b.confirmed_count for b in batches),
            redeemed=len(matched),
            flagged=len(records) - len(matched),
        ),
        recent_batches=recent_batches,
        open_alert_list=open_alert_list,
    )
