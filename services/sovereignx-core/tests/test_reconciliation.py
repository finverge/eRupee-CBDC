"""run_reconciliation_cycle() (app/routers/reconciliation.py) — the shared
function both the admin "Run Reconciliation" button and main.py's
unattended background loop call. ledger_client's HTTP calls are
monkeypatched here (not respx) since we're testing the orchestration
logic, not the HTTP client itself — see test_ledger_client.py for that."""
from datetime import datetime, timezone

import pytest

from app.models import Scheme, Beneficiary, DisbursementBatch, IssuanceInstruction, ReconciliationRecord, AgentDailyReconciliation
from app.models import SchemeStatus, EligibilityStatus, ConsentStatus, BatchStatus, InstructionStatus
from app.routers.reconciliation import run_reconciliation_cycle
from app.services import ledger_client


def _make_instruction(db, beneficiary_ref="BEN-001", external_id="EXT-001"):
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
        external_instruction_id=external_id, batch_id=batch.id, beneficiary_id=beneficiary.id,
        beneficiary_ref=beneficiary_ref, amount_paisa=100000, status=InstructionStatus.CONFIRMED,
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return instruction


def test_matched_redemption_creates_a_reconciliation_record(db_session, monkeypatch):
    instruction = _make_instruction(db_session, beneficiary_ref="BEN-001")
    acked = []

    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [{
        "id": "RDM-001", "beneficiary_ref": "BEN-001", "merchant_ref": "MER-001",
        "merchant_category": "GROCERY", "amount_paisa": 5000, "rule_check_result": "allowed", "executed": True,
    }])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: acked.append(rid))
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [])

    result = run_reconciliation_cycle(db_session)

    assert result.pulled == 1
    assert result.matched == 1
    assert result.blocked == 0
    assert acked == ["RDM-001"]

    record = db_session.query(ReconciliationRecord).filter(ReconciliationRecord.instruction_id == instruction.id).first()
    assert record is not None
    assert record.match_status == "matched"


def test_blocked_redemption_raises_a_compliance_alert(db_session, monkeypatch):
    _make_instruction(db_session, beneficiary_ref="BEN-001")

    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [{
        "id": "RDM-001", "beneficiary_ref": "BEN-001", "merchant_ref": "MER-002",
        "merchant_category": "FUEL", "amount_paisa": 5000, "rule_check_result": "blocked_merchant_category", "executed": False,
    }])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: None)
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [])

    result = run_reconciliation_cycle(db_session)

    assert result.blocked == 1
    assert result.new_alerts >= 1


def test_redemption_with_no_matching_instruction_is_acked_and_skipped(db_session, monkeypatch):
    acked = []
    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [{
        "id": "RDM-ORPHAN", "beneficiary_ref": "BEN-NEVER-ISSUED-TO", "merchant_ref": "MER-001",
        "merchant_category": "GROCERY", "amount_paisa": 5000, "rule_check_result": "allowed", "executed": True,
    }])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: acked.append(rid))
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [])

    result = run_reconciliation_cycle(db_session)

    assert result.matched == 0
    assert result.blocked == 0
    assert acked == ["RDM-ORPHAN"]
    assert db_session.query(ReconciliationRecord).count() == 0


def test_agent_daily_summary_is_upserted_not_duplicated_on_repeat_runs(db_session, monkeypatch):
    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: None)
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [{"agent_ref": "AGT-001"}])
    monkeypatch.setattr(ledger_client, "get_agent_daily_summary", lambda ref: {
        "agent_ref": "AGT-001", "date": "2026-09-28", "transaction_count": 2, "total_amount_paisa": 9000, "daily_limit_paisa": 50000,
    })

    run_reconciliation_cycle(db_session)
    run_reconciliation_cycle(db_session)
    run_reconciliation_cycle(db_session)

    rows = db_session.query(AgentDailyReconciliation).filter(
        AgentDailyReconciliation.agent_ref == "AGT-001", AgentDailyReconciliation.date == "2026-09-28",
    ).all()
    assert len(rows) == 1
    assert rows[0].transaction_count == 2


def test_agent_daily_summary_updates_in_place_when_activity_changes(db_session, monkeypatch):
    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: None)
    monkeypatch.setattr(ledger_client, "list_agents", lambda: [{"agent_ref": "AGT-001"}])

    monkeypatch.setattr(ledger_client, "get_agent_daily_summary", lambda ref: {
        "agent_ref": "AGT-001", "date": "2026-09-28", "transaction_count": 1, "total_amount_paisa": 1000, "daily_limit_paisa": 50000,
    })
    run_reconciliation_cycle(db_session)

    monkeypatch.setattr(ledger_client, "get_agent_daily_summary", lambda ref: {
        "agent_ref": "AGT-001", "date": "2026-09-28", "transaction_count": 5, "total_amount_paisa": 9000, "daily_limit_paisa": 50000,
    })
    run_reconciliation_cycle(db_session)

    row = db_session.query(AgentDailyReconciliation).filter(AgentDailyReconciliation.agent_ref == "AGT-001").one()
    assert row.transaction_count == 5
    assert row.total_amount_paisa == 9000


def test_ledger_simulator_unreachable_for_agent_pull_does_not_crash_the_run(db_session, monkeypatch):
    import httpx

    monkeypatch.setattr(ledger_client, "pull_unreconciled_redemptions", lambda: [])
    monkeypatch.setattr(ledger_client, "ack_redemption", lambda rid: None)

    def _raise(*a, **k):
        raise httpx.ConnectError("simulated outage")
    monkeypatch.setattr(ledger_client, "list_agents", _raise)

    result = run_reconciliation_cycle(db_session)
    assert result.agent_summaries_pulled == 0
