"""Offline transaction queue — FSD FR-26–FR-28, HLD Section 9.2. A device
registers once (getting a device_secret back — a real deployment would
provision this via the bank's own device-binding flow, e.g. at first
login with connectivity, not return it plainly like this simulator does).
While offline, the Wallet SDK queues signed transactions locally
(sdk/wallet-sdk/src/offlineQueue.ts) and later calls POST .../sync with
the whole batch. Each queued transaction carries an HMAC-SHA256 signature
over its own fields, keyed by device_secret — a replayed or tampered
queue entry fails signature verification here and is rejected, not
trusted blindly (HLD 9.2). client_tx_id is the idempotency key: a sync
retried after a dropped response must not double-spend.
"""
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DeviceRegistration, OfflineQueueSubmission, Wallet, Merchant
from app.routers.redemption import execute_redemption
from app.schemas import DeviceRegisterIn, DeviceRegisterOut, OfflineSyncIn, OfflineSyncOut, OfflineSyncResultItem
import secrets

router = APIRouter(prefix="/offline", tags=["offline"])


@router.post("/devices/register", response_model=DeviceRegisterOut, status_code=201)
def register_device(payload: DeviceRegisterIn, db: Session = Depends(get_db)):
    existing = db.query(DeviceRegistration).filter(DeviceRegistration.device_id == payload.device_id).first()
    if existing:
        raise HTTPException(409, "Device already registered")
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == payload.beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary — cannot bind a device to it yet")

    device = DeviceRegistration(
        device_id=payload.device_id, beneficiary_ref=payload.beneficiary_ref,
        device_secret=secrets.token_hex(16),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _verify_signature(device: DeviceRegistration, tx) -> bool:
    # tx.queued_at is the RAW string the device signed (schemas.py's
    # QueuedTransaction docstring) — never re-serialize a parsed datetime
    # here, or every signature breaks the moment JS's and Python's ISO
    # formatting disagree (they do: 'Z'+3-digit ms vs '+00:00'+6-digit us).
    message = f"{tx.client_tx_id}|{tx.merchant_ref}|{tx.amount_paisa}|{tx.queued_at}"
    expected = hmac.new(device.device_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, tx.signature)


def _parse_queued_at(raw: str) -> datetime:
    """Only for writing to the DB column — never for re-deriving the
    signed message (see _verify_signature)."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


@router.post("/sync", response_model=OfflineSyncOut)
def sync_offline_queue(payload: OfflineSyncIn, db: Session = Depends(get_db)):
    device = db.query(DeviceRegistration).filter(DeviceRegistration.device_id == payload.device_id).first()
    if not device:
        raise HTTPException(404, "Device not registered")

    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == device.beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this device's beneficiary")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    already_today = db.query(OfflineQueueSubmission).filter(
        OfflineQueueSubmission.device_id == device.device_id,
        OfflineQueueSubmission.synced_at >= today_start,
        OfflineQueueSubmission.executed == True,  # noqa: E712
    ).all()
    spent_today = sum(s.amount_paisa for s in already_today)
    count_today = len(already_today)

    results: list[OfflineSyncResultItem] = []

    # Process in the order the device queued them — earliest first —
    # since caps are evaluated cumulatively (HLD 9.2's exposure-bounding).
    for tx in sorted(payload.transactions, key=lambda t: t.queued_at):
        existing = db.query(OfflineQueueSubmission).filter(OfflineQueueSubmission.client_tx_id == tx.client_tx_id).first()
        if existing:
            results.append(OfflineSyncResultItem(client_tx_id=tx.client_tx_id, outcome="already_synced", executed=existing.executed))
            continue

        if not _verify_signature(device, tx):
            submission = OfflineQueueSubmission(
                device_id=device.device_id, client_tx_id=tx.client_tx_id, beneficiary_ref=device.beneficiary_ref,
                merchant_ref=tx.merchant_ref, amount_paisa=tx.amount_paisa, queued_at=_parse_queued_at(tx.queued_at),
                outcome="bad_signature", executed=False,
            )
            db.add(submission)
            results.append(OfflineSyncResultItem(client_tx_id=tx.client_tx_id, outcome="bad_signature", executed=False))
            continue

        if count_today + 1 > device.daily_cap_count or spent_today + tx.amount_paisa > device.daily_cap_paisa:
            submission = OfflineQueueSubmission(
                device_id=device.device_id, client_tx_id=tx.client_tx_id, beneficiary_ref=device.beneficiary_ref,
                merchant_ref=tx.merchant_ref, amount_paisa=tx.amount_paisa, queued_at=_parse_queued_at(tx.queued_at),
                outcome="cap_exceeded", executed=False,
            )
            db.add(submission)
            results.append(OfflineSyncResultItem(client_tx_id=tx.client_tx_id, outcome="cap_exceeded", executed=False))
            continue

        merchant = db.query(Merchant).filter(Merchant.merchant_ref == tx.merchant_ref).first()
        if not merchant:
            submission = OfflineQueueSubmission(
                device_id=device.device_id, client_tx_id=tx.client_tx_id, beneficiary_ref=device.beneficiary_ref,
                merchant_ref=tx.merchant_ref, amount_paisa=tx.amount_paisa, queued_at=_parse_queued_at(tx.queued_at),
                outcome="merchant_not_found", executed=False,
            )
            db.add(submission)
            results.append(OfflineSyncResultItem(client_tx_id=tx.client_tx_id, outcome="merchant_not_found", executed=False))
            continue

        redemption = execute_redemption(db, wallet, merchant, tx.amount_paisa)
        submission = OfflineQueueSubmission(
            device_id=device.device_id, client_tx_id=tx.client_tx_id, beneficiary_ref=device.beneficiary_ref,
            merchant_ref=tx.merchant_ref, amount_paisa=tx.amount_paisa, queued_at=_parse_queued_at(tx.queued_at),
            outcome=redemption.rule_check_result.value, executed=redemption.executed,
        )
        db.add(submission)
        if redemption.executed:
            spent_today += tx.amount_paisa
            count_today += 1
        results.append(OfflineSyncResultItem(client_tx_id=tx.client_tx_id, outcome=submission.outcome, executed=redemption.executed))

    db.commit()
    return OfflineSyncOut(results=results)
