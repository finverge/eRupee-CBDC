"""Simulated Fraud360 / AML360 CBDC rule pack (FSD Section 4, FR-16–FR-18).

This is a real, running rule engine — not a fabricated connection to the
actual Fraud360/AML360 products (this codebase holds no credentials for
either). It implements the same two rule categories the FSD specifies for
the CBDC rule pack: rule-violating redemptions, and velocity anomalies.
Swapping this module for a real Fraud360/AML360 API call is a service
boundary this file exists specifically to make easy — every caller here
only depends on `evaluate_redemption`'s return value, not on how it was
computed.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ComplianceAlert, ReconciliationRecord

_REASON_LABELS = {
    "blocked_expired": "Expired token redemption",
    "blocked_merchant_category": "Merchant category mismatch",
    "blocked_insufficient_balance": "Insufficient balance at redemption",
    "blocked_geo_fence": "Geo-fence violation",
    "blocked_single_use": "Duplicate wallet linkage / re-use of single-use token",
}


def evaluate_redemption(db: Session, beneficiary_ref: str, rule_check_result: str, amount_paisa: int) -> list[ComplianceAlert]:
    """Called once per redemption event pulled from the ledger simulator
    (app/services/reconciliation.py). Returns any new alerts raised —
    caller is responsible for adding them to the session."""
    alerts: list[ComplianceAlert] = []

    if rule_check_result != "allowed":
        label = _REASON_LABELS.get(rule_check_result, rule_check_result)
        alerts.append(ComplianceAlert(
            source="Fraud360",
            beneficiary_ref=beneficiary_ref,
            rule_triggered=label,
            detail=f"Redemption of ₹{amount_paisa / 100:.2f} was blocked at the ledger: {label}.",
        ))

    velocity_alert = _check_velocity(db, beneficiary_ref)
    if velocity_alert:
        alerts.append(velocity_alert)

    return alerts


def _check_velocity(db: Session, beneficiary_ref: str) -> ComplianceAlert | None:
    from app.models import IssuanceInstruction

    window_start = datetime.now(timezone.utc) - timedelta(minutes=settings.velocity_window_minutes)
    recent = (
        db.query(ReconciliationRecord)
        .join(IssuanceInstruction, ReconciliationRecord.instruction_id == IssuanceInstruction.id)
        .filter(IssuanceInstruction.beneficiary_ref == beneficiary_ref, ReconciliationRecord.created_at >= window_start)
        .count()
    )
    if recent + 1 >= settings.velocity_max_attempts:
        return ComplianceAlert(
            source="Fraud360",
            beneficiary_ref=beneficiary_ref,
            rule_triggered="Velocity anomaly",
            detail=f"{recent + 1} redemption attempts by this beneficiary within {settings.velocity_window_minutes} minutes.",
        )
    return None
