"""app/services/compliance.py — the simulated Fraud360/AML360 CBDC rule
pack: rule-violating redemptions and velocity anomalies."""
from datetime import datetime, timezone

from app.config import settings
from app.models import Scheme, Beneficiary, DisbursementBatch, IssuanceInstruction, ReconciliationRecord
from app.models import SchemeStatus, EligibilityStatus, ConsentStatus, BatchStatus, InstructionStatus
from app.services.compliance import evaluate_redemption


def _make_instruction(db, beneficiary_ref="BEN-001"):
    scheme = Scheme(
        name="Test Scheme", department="Test Dept", benefit_amount_paisa=100000,
        validity_start=datetime.now(timezone.utc), validity_end=datetime.now(timezone.utc),
        status=SchemeStatus.ACTIVE, created_by="tester",
    )
    db.add(scheme)
    db.flush()
    beneficiary = Beneficiary(
        scheme_id=scheme.id, beneficiary_ref=beneficiary_ref, full_name="Test Beneficiary", district="Test District",
        eligibility_status=EligibilityStatus.ELIGIBLE, consent_status=ConsentStatus.GRANTED,
    )
    db.add(beneficiary)
    db.flush()
    batch = DisbursementBatch(scheme_id=scheme.id, status=BatchStatus.CONFIRMED, triggered_by="tester")
    db.add(batch)
    db.flush()
    instruction = IssuanceInstruction(
        external_instruction_id=f"EXT-{beneficiary_ref}", batch_id=batch.id, beneficiary_id=beneficiary.id,
        beneficiary_ref=beneficiary_ref, amount_paisa=100000, status=InstructionStatus.CONFIRMED,
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return instruction


def test_allowed_redemption_raises_no_rule_alert(db_session):
    alerts = evaluate_redemption(db_session, "BEN-001", "allowed", 5000)
    rule_alerts = [a for a in alerts if a.rule_triggered != "Velocity anomaly"]
    assert rule_alerts == []


def test_blocked_redemption_raises_a_labeled_alert(db_session):
    alerts = evaluate_redemption(db_session, "BEN-001", "blocked_merchant_category", 5000)
    rule_alerts = [a for a in alerts if a.rule_triggered != "Velocity anomaly"]
    assert len(rule_alerts) == 1
    assert rule_alerts[0].rule_triggered == "Merchant category mismatch"
    assert rule_alerts[0].source == "Fraud360"


def test_unrecognized_rule_result_still_raises_an_alert_with_a_fallback_label(db_session):
    alerts = evaluate_redemption(db_session, "BEN-001", "some_future_rule_code", 5000)
    rule_alerts = [a for a in alerts if a.rule_triggered != "Velocity anomaly"]
    assert rule_alerts[0].rule_triggered == "some_future_rule_code"


def test_velocity_anomaly_fires_after_max_attempts_within_the_window(db_session):
    instruction = _make_instruction(db_session, beneficiary_ref="BEN-VELOCITY")

    # Simulate (velocity_max_attempts - 1) prior redemptions already
    # reconciled within the window — the Nth evaluate_redemption call
    # (counting itself) should be the one that trips the alarm.
    for i in range(settings.velocity_max_attempts - 1):
        db_session.add(ReconciliationRecord(
            instruction_id=instruction.id, external_redemption_id=f"RDM-{i}",
            merchant_ref="MER-001", merchant_category="GROCERY", amount_paisa=1000,
            rule_check_result="allowed", match_status="matched",
        ))
    db_session.commit()

    alerts = evaluate_redemption(db_session, "BEN-VELOCITY", "allowed", 1000)
    velocity_alerts = [a for a in alerts if a.rule_triggered == "Velocity anomaly"]
    assert len(velocity_alerts) == 1


def test_velocity_anomaly_does_not_fire_below_the_threshold(db_session):
    instruction = _make_instruction(db_session, beneficiary_ref="BEN-CALM")
    db_session.add(ReconciliationRecord(
        instruction_id=instruction.id, external_redemption_id="RDM-CALM-1",
        merchant_ref="MER-001", merchant_category="GROCERY", amount_paisa=1000,
        rule_check_result="allowed", match_status="matched",
    ))
    db_session.commit()

    alerts = evaluate_redemption(db_session, "BEN-CALM", "allowed", 1000)
    velocity_alerts = [a for a in alerts if a.rule_triggered == "Velocity anomaly"]
    assert velocity_alerts == []
