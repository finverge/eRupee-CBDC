"""app/services/ledger_client.py — the one file every ledger-affecting
call in this service must go through. `respx` mocks the actual HTTP
boundary so these tests never depend on erupee-ledger-simulator running,
and prove ledger_client sends the right request shape and handles error
responses correctly regardless."""
import httpx
import pytest
import respx

from app.config import settings
from app.services import ledger_client

BASE = settings.ledger_sim_url


@respx.mock
def test_submit_issuance_sends_expected_payload_and_headers():
    route = respx.post(f"{BASE}/issuance").mock(
        return_value=httpx.Response(201, json={"id": "INS-001", "status": "confirmed"})
    )

    result = ledger_client.submit_issuance(
        external_instruction_id="EXT-001", beneficiary_ref="BEN-001", amount_paisa=50000,
        scheme_ref="SCH-001", expires_at=None, merchant_categories=["GROCERY"], single_use=False,
    )

    assert result["id"] == "INS-001"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-Service-Key"] == settings.ledger_sim_service_key
    import json
    body = json.loads(sent.content)
    assert body["beneficiary_ref"] == "BEN-001"
    assert body["rules"]["merchant_categories"] == ["GROCERY"]


@respx.mock
def test_pull_unreconciled_redemptions_uses_the_filter_param():
    route = respx.get(f"{BASE}/redemptions").mock(return_value=httpx.Response(200, json=[{"id": "RDM-001"}]))

    result = ledger_client.pull_unreconciled_redemptions()

    assert result == [{"id": "RDM-001"}]
    assert route.calls.last.request.url.params["since_unpulled_only"] == "true"


@respx.mock
def test_get_wallet_returns_none_on_404_instead_of_raising():
    respx.get(f"{BASE}/wallets/BEN-UNKNOWN").mock(return_value=httpx.Response(404))
    assert ledger_client.get_wallet("BEN-UNKNOWN") is None


@respx.mock
def test_get_wallet_returns_data_on_success():
    respx.get(f"{BASE}/wallets/BEN-001").mock(return_value=httpx.Response(200, json={"beneficiary_ref": "BEN-001", "balance_paisa": 5000}))
    result = ledger_client.get_wallet("BEN-001")
    assert result["balance_paisa"] == 5000


@respx.mock
def test_a_5xx_from_the_ledger_simulator_raises():
    respx.get(f"{BASE}/redemptions").mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        ledger_client.pull_unreconciled_redemptions()


@respx.mock
def test_onboard_agent_sends_the_password_field():
    route = respx.post(f"{BASE}/agents").mock(return_value=httpx.Response(201, json={"agent_ref": "AGT-999"}))

    ledger_client.onboard_agent("AGT-999", "New Agent", "Test Region", 5000000, "SomePassword123!")

    import json
    body = json.loads(route.calls.last.request.content)
    assert body["password"] == "SomePassword123!"


@respx.mock
def test_get_agent_daily_summary_does_not_send_service_key():
    """agents.py's daily-summary route on the ledger simulator is
    intentionally public (see the module's own comment) — this locks that
    in so a future change doesn't silently start sending a header the
    receiving route doesn't expect and doesn't need."""
    route = respx.get(f"{BASE}/agents/AGT-001/daily-summary").mock(
        return_value=httpx.Response(200, json={"agent_ref": "AGT-001"})
    )
    ledger_client.get_agent_daily_summary("AGT-001")
    assert "X-Service-Key" not in route.calls.last.request.headers
