"""The programmable-rule engine (app/routers/redemption.py) is the core
regulatory promise of this product — money that says where and how it can
be spent. These tests exercise it through the real HTTP endpoint, not by
calling execute_redemption() directly, so a routing/serialization
regression would fail here too."""
from datetime import datetime, timedelta, timezone

from app.models import Wallet, Merchant, IssuanceInstruction, InstructionStatus


def _make_wallet(db, beneficiary_ref="BEN-TEST-001", balance_paisa=100000):
    wallet = Wallet(beneficiary_ref=beneficiary_ref, balance_paisa=balance_paisa)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def _make_merchant(db, merchant_ref="MER-TEST-001", category="GROCERY"):
    merchant = Merchant(merchant_ref=merchant_ref, name="Test Merchant", category=category)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


def _make_instruction(db, wallet, rules=None, amount_paisa=100000):
    instruction = IssuanceInstruction(
        external_instruction_id=f"EXT-{wallet.id}", wallet_id=wallet.id, beneficiary_ref=wallet.beneficiary_ref,
        amount_paisa=amount_paisa, status=InstructionStatus.CONFIRMED, rules=rules or {},
    )
    db.add(instruction)
    db.commit()
    db.refresh(instruction)
    return instruction


def test_allowed_redemption_moves_balance(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session, balance_paisa=50000)
    merchant = _make_merchant(db_session)
    _make_instruction(db_session, wallet)

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 10000,
    })

    assert resp.status_code == 201
    body = resp.json()
    assert body["executed"] is True
    assert body["rule_check_result"] == "allowed"

    db_session.refresh(wallet)
    db_session.refresh(merchant)
    assert wallet.balance_paisa == 40000
    assert merchant.settlement_balance_paisa == 10000


def test_insufficient_balance_blocks_and_leaves_balance_unchanged(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session, balance_paisa=500)
    merchant = _make_merchant(db_session)
    _make_instruction(db_session, wallet)

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 10000,
    })

    assert resp.status_code == 201
    body = resp.json()
    assert body["executed"] is False
    assert body["rule_check_result"] == "blocked_insufficient_balance"

    db_session.refresh(wallet)
    assert wallet.balance_paisa == 500


def test_merchant_category_lock_blocks_wrong_category(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session)
    merchant = _make_merchant(db_session, category="FUEL")
    _make_instruction(db_session, wallet, rules={"merchant_categories": ["FERTILIZER"]})

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })

    body = resp.json()
    assert body["executed"] is False
    assert body["rule_check_result"] == "blocked_merchant_category"


def test_merchant_category_lock_allows_matching_category(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session)
    merchant = _make_merchant(db_session, category="FERTILIZER")
    _make_instruction(db_session, wallet, rules={"merchant_categories": ["FERTILIZER", "GROCERY"]})

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })

    assert resp.json()["executed"] is True


def test_expired_instruction_blocks_redemption(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session)
    merchant = _make_merchant(db_session)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _make_instruction(db_session, wallet, rules={"expires_at": past})

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })

    body = resp.json()
    assert body["executed"] is False
    assert body["rule_check_result"] == "blocked_expired"


def test_unexpired_instruction_allows_redemption(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session)
    merchant = _make_merchant(db_session)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    _make_instruction(db_session, wallet, rules={"expires_at": future})

    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })

    assert resp.json()["executed"] is True


def test_single_use_instruction_blocks_second_redemption(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session, balance_paisa=100000)
    merchant = _make_merchant(db_session)
    _make_instruction(db_session, wallet, rules={"single_use": True})

    first = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })
    assert first.json()["executed"] is True

    second = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 5000,
    })
    body = second.json()
    assert body["executed"] is False
    assert body["rule_check_result"] == "blocked_single_use"


def test_redeem_unknown_beneficiary_is_404(client, db_session, service_key_headers):
    merchant = _make_merchant(db_session)
    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": "BEN-DOES-NOT-EXIST", "merchant_ref": merchant.merchant_ref, "amount_paisa": 1000,
    })
    assert resp.status_code == 404


def test_redeem_unknown_merchant_is_404(client, db_session, service_key_headers):
    wallet = _make_wallet(db_session)
    resp = client.post("/redemptions", headers=service_key_headers, json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": "MER-DOES-NOT-EXIST", "amount_paisa": 1000,
    })
    assert resp.status_code == 404


def test_redeem_without_service_key_is_401(client, db_session):
    wallet = _make_wallet(db_session)
    merchant = _make_merchant(db_session)
    resp = client.post("/redemptions", json={
        "beneficiary_ref": wallet.beneficiary_ref, "merchant_ref": merchant.merchant_ref, "amount_paisa": 1000,
    })
    assert resp.status_code == 401
