"""Offline queue sync (app/routers/offline.py). _verify_signature must
check the RAW queued_at string the device signed — this is the exact spot
where a previous version of this code re-serialized a parsed datetime
before verifying, breaking every signature the moment Python's and JS's
ISO formatting disagreed. test_signature_survives_a_javascript_style_
timestamp below is a direct regression test for that."""
import hashlib
import hmac
from datetime import datetime, timezone

from app.models import Wallet, Merchant, DeviceRegistration


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


def _sign(device_secret: str, client_tx_id: str, merchant_ref: str, amount_paisa: int, queued_at: str) -> str:
    message = f"{client_tx_id}|{merchant_ref}|{amount_paisa}|{queued_at}"
    return hmac.new(device_secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _register_device(client, beneficiary_ref="BEN-TEST-001", device_id="DEV-TEST-001"):
    resp = client.post("/offline/devices/register", json={"device_id": device_id, "beneficiary_ref": beneficiary_ref})
    return resp.json()


def test_register_device_returns_a_secret(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    body = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    assert body["device_secret"]
    assert body["device_id"] == "DEV-001"


def test_register_device_twice_is_409(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001")
    _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    resp = client.post("/offline/devices/register", json={"device_id": "DEV-001", "beneficiary_ref": "BEN-001"})
    assert resp.status_code == 409


def test_valid_signature_syncs_and_executes(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=50000)
    _make_merchant(db_session, merchant_ref="MER-001")
    device = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    secret = device["device_secret"]

    queued_at = datetime.now(timezone.utc).isoformat()
    sig = _sign(secret, "TX-001", "MER-001", 5000, queued_at)

    resp = client.post("/offline/sync", json={
        "device_id": "DEV-001",
        "transactions": [{"client_tx_id": "TX-001", "merchant_ref": "MER-001", "amount_paisa": 5000, "queued_at": queued_at, "signature": sig}],
    })
    result = resp.json()["results"][0]
    assert result["executed"] is True
    assert result["outcome"] == "allowed"


def test_signature_survives_a_javascript_style_timestamp(client, db_session):
    """JS's Date().toISOString() produces '...Z' with exactly 3 fractional
    digits — different from Python's isoformat(). The signature must
    verify against exactly that raw string, unmodified."""
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=50000)
    _make_merchant(db_session, merchant_ref="MER-001")
    device = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    secret = device["device_secret"]

    js_style_queued_at = "2026-09-28T09:15:30.123Z"
    sig = _sign(secret, "TX-JS-001", "MER-001", 2500, js_style_queued_at)

    resp = client.post("/offline/sync", json={
        "device_id": "DEV-001",
        "transactions": [{"client_tx_id": "TX-JS-001", "merchant_ref": "MER-001", "amount_paisa": 2500, "queued_at": js_style_queued_at, "signature": sig}],
    })
    result = resp.json()["results"][0]
    assert result["outcome"] != "bad_signature"
    assert result["executed"] is True


def test_tampered_amount_fails_signature(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=50000)
    _make_merchant(db_session, merchant_ref="MER-001")
    device = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    secret = device["device_secret"]

    queued_at = datetime.now(timezone.utc).isoformat()
    sig = _sign(secret, "TX-001", "MER-001", 5000, queued_at)  # signed for 5000...

    resp = client.post("/offline/sync", json={
        "device_id": "DEV-001",
        # ...but submitted claiming 500000 — signature must not match
        "transactions": [{"client_tx_id": "TX-001", "merchant_ref": "MER-001", "amount_paisa": 500000, "queued_at": queued_at, "signature": sig}],
    })
    result = resp.json()["results"][0]
    assert result["outcome"] == "bad_signature"
    assert result["executed"] is False


def test_replayed_client_tx_id_is_idempotent_not_double_spent(client, db_session):
    wallet = _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=50000)
    _make_merchant(db_session, merchant_ref="MER-001")
    device = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    secret = device["device_secret"]

    queued_at = datetime.now(timezone.utc).isoformat()
    sig = _sign(secret, "TX-001", "MER-001", 5000, queued_at)
    payload = {
        "device_id": "DEV-001",
        "transactions": [{"client_tx_id": "TX-001", "merchant_ref": "MER-001", "amount_paisa": 5000, "queued_at": queued_at, "signature": sig}],
    }

    client.post("/offline/sync", json=payload)
    second = client.post("/offline/sync", json=payload)  # retried sync, e.g. after a dropped response

    result = second.json()["results"][0]
    assert result["outcome"] == "already_synced"

    db_session.refresh(wallet)
    assert wallet.balance_paisa == 45000  # debited exactly once, not twice


def test_daily_cap_count_exceeded(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", balance_paisa=1000000)
    _make_merchant(db_session, merchant_ref="MER-001")
    device = _register_device(client, beneficiary_ref="BEN-001", device_id="DEV-001")
    secret = device["device_secret"]
    daily_cap_count = device["daily_cap_count"]

    txs = []
    for i in range(daily_cap_count + 1):
        queued_at = datetime.now(timezone.utc).isoformat()
        client_tx_id = f"TX-{i}"
        sig = _sign(secret, client_tx_id, "MER-001", 100, queued_at)
        txs.append({"client_tx_id": client_tx_id, "merchant_ref": "MER-001", "amount_paisa": 100, "queued_at": queued_at, "signature": sig})

    resp = client.post("/offline/sync", json={"device_id": "DEV-001", "transactions": txs})
    outcomes = [r["outcome"] for r in resp.json()["results"]]
    assert outcomes.count("cap_exceeded") == 1
    assert outcomes.count("allowed") == daily_cap_count


def test_sync_unregistered_device_is_404(client, db_session):
    resp = client.post("/offline/sync", json={"device_id": "DEV-NOT-REGISTERED", "transactions": []})
    assert resp.status_code == 404
