"""USSD PIN brute-force lockout (app/routers/ussd.py). This is the exact
code path where the Postgres-timezone bug lived: a 15-minute lockout was
silently measuring itself as 345 minutes because `.replace(tzinfo=
timezone.utc)` mislabeled an IST-aware datetime instead of converting it.
test_lockout_window_is_close_to_configured_minutes below is a direct
regression test for that fix — it would have failed loudly before the
app/timeutil.py::as_utc() fix landed."""
from datetime import datetime, timezone

from app.models import Wallet
from app.config import settings


def _make_wallet(db, beneficiary_ref="BEN-TEST-001", pin="1234"):
    wallet = Wallet(beneficiary_ref=beneficiary_ref, balance_paisa=10000, ussd_pin=pin)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def _dial_and_enter_ref(client, beneficiary_ref):
    session_id = client.post("/ussd/dial").json()["session_id"]
    client.post(f"/ussd/{session_id}/input", json={"input": beneficiary_ref})
    return session_id


def test_correct_pin_reaches_main_menu(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")
    session_id = _dial_and_enter_ref(client, "BEN-001")

    resp = client.post(f"/ussd/{session_id}/input", json={"input": "1234"})
    assert "Check Balance" in resp.json()["screen_text"]
    assert resp.json()["session_ended"] is False


def test_wrong_pin_ends_session_but_does_not_lock_on_first_attempt(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")
    session_id = _dial_and_enter_ref(client, "BEN-001")

    resp = client.post(f"/ussd/{session_id}/input", json={"input": "0000"})
    assert resp.json()["session_ended"] is True
    assert "Incorrect PIN" in resp.json()["screen_text"]
    assert "locked" not in resp.json()["screen_text"].lower()


def test_three_wrong_pins_locks_the_account(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")

    for _ in range(settings.ussd_pin_max_attempts - 1):
        sid = _dial_and_enter_ref(client, "BEN-001")
        client.post(f"/ussd/{sid}/input", json={"input": "0000"})

    sid = _dial_and_enter_ref(client, "BEN-001")
    resp = client.post(f"/ussd/{sid}/input", json={"input": "0000"})
    assert "locked" in resp.json()["screen_text"].lower()


def test_locked_account_rejects_even_the_correct_pin(client, db_session):
    wallet = _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")

    for _ in range(settings.ussd_pin_max_attempts):
        sid = _dial_and_enter_ref(client, "BEN-001")
        client.post(f"/ussd/{sid}/input", json={"input": "0000"})

    db_session.refresh(wallet)
    assert wallet.pin_locked_until is not None

    sid = _dial_and_enter_ref(client, "BEN-001")
    resp = client.post(f"/ussd/{sid}/input", json={"input": "1234"})
    assert "locked" in resp.json()["screen_text"].lower()


def test_lockout_window_is_close_to_configured_minutes(client, db_session):
    """Regression test for the timezone bug: the persisted pin_locked_until
    must land within a couple of minutes of "now + ussd_pin_lockout_minutes"
    — before the fix this was off by ~5.5 hours on this machine's Postgres
    (session TimeZone=Asia/Calcutta)."""
    wallet = _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")

    for _ in range(settings.ussd_pin_max_attempts):
        sid = _dial_and_enter_ref(client, "BEN-001")
        client.post(f"/ussd/{sid}/input", json={"input": "0000"})

    db_session.refresh(wallet)
    locked_until = wallet.pin_locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    else:
        locked_until = locked_until.astimezone(timezone.utc)

    minutes_ahead = (locked_until - datetime.now(timezone.utc)).total_seconds() / 60
    assert abs(minutes_ahead - settings.ussd_pin_lockout_minutes) < 2, (
        f"expected lockout ~{settings.ussd_pin_lockout_minutes} min ahead, got {minutes_ahead:.1f} min "
        "(a large discrepancy like this is exactly the symptom of the tzinfo relabeling bug)"
    )


def test_correct_pin_resets_failed_attempts(client, db_session):
    wallet = _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")

    sid = _dial_and_enter_ref(client, "BEN-001")
    client.post(f"/ussd/{sid}/input", json={"input": "0000"})

    sid = _dial_and_enter_ref(client, "BEN-001")
    client.post(f"/ussd/{sid}/input", json={"input": "1234"})

    db_session.refresh(wallet)
    assert wallet.failed_pin_attempts == 0
    assert wallet.pin_locked_until is None


def test_balance_enquiry_over_ussd(client, db_session):
    _make_wallet(db_session, beneficiary_ref="BEN-001", pin="1234")
    sid = _dial_and_enter_ref(client, "BEN-001")
    client.post(f"/ussd/{sid}/input", json={"input": "1234"})

    resp = client.post(f"/ussd/{sid}/input", json={"input": "1"})
    assert "Balance" in resp.json()["screen_text"]


def test_unknown_beneficiary_ref_ends_session(client, db_session):
    session_id = client.post("/ussd/dial").json()["session_id"]
    resp = client.post(f"/ussd/{session_id}/input", json={"input": "BEN-DOES-NOT-EXIST"})
    assert resp.json()["session_ended"] is True
