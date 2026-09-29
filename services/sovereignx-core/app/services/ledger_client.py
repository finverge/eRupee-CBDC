"""HTTP client for the erupee-ledger-simulator service — this IS the
SovereignX e₹ Connector Adapter described in HLD Section 4.3, talking to
a simulated sponsor bank instead of a real one. Every other module in
this service reaches the ledger only through these functions, so pointing
at a real bank connector later means changing this file (and
config.settings.ledger_sim_url/service_key), not any caller."""
import httpx

from app.config import settings

_headers = {"X-Service-Key": settings.ledger_sim_service_key}


def submit_issuance(external_instruction_id: str, beneficiary_ref: str, amount_paisa: int,
                     scheme_ref: str, expires_at: str | None, merchant_categories: list[str],
                     single_use: bool) -> dict:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.post("/issuance", headers=_headers, json={
            "external_instruction_id": external_instruction_id,
            "beneficiary_ref": beneficiary_ref,
            "amount_paisa": amount_paisa,
            "scheme_ref": scheme_ref,
            "rules": {
                "expires_at": expires_at,
                "merchant_categories": merchant_categories or None,
                "single_use": single_use,
            },
        })
        resp.raise_for_status()
        return resp.json()


def pull_unreconciled_redemptions() -> list[dict]:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.get("/redemptions", headers=_headers, params={"since_unpulled_only": "true"})
        resp.raise_for_status()
        return resp.json()


def ack_redemption(redemption_id: str) -> None:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.post(f"/redemptions/{redemption_id}/ack", headers=_headers)
        resp.raise_for_status()


def get_wallet(beneficiary_ref: str) -> dict | None:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.get(f"/wallets/{beneficiary_ref}", headers=_headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


# ---------- Agent-assisted channel (FSD FR-29–FR-32) ----------
# Proxied through sovereignx-core rather than called directly from the
# browser — the onboard/list endpoints require the ledger simulator's
# service key (app/security.py's require_service_key there), which must
# never reach a frontend bundle. This is the same server-side-secret
# boundary every other ledger_client function in this file already keeps;
# see sovereignx-core/app/routers/agents.py for the console-facing side.

def onboard_agent(agent_ref: str, name: str, assigned_region: str, daily_limit_paisa: int, password: str) -> dict:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.post("/agents", headers=_headers, json={
            "agent_ref": agent_ref, "name": name, "assigned_region": assigned_region,
            "daily_limit_paisa": daily_limit_paisa, "password": password,
        })
        resp.raise_for_status()
        return resp.json()


def list_agents() -> list[dict]:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.get("/agents", headers=_headers)
        resp.raise_for_status()
        return resp.json()


def get_agent_daily_summary(agent_ref: str) -> dict:
    # No X-Service-Key on this one server-side either (agents.py's
    # daily-summary route is public, same as its lookup route) — routed
    # through sovereignx-core anyway for one reason: consistency (every
    # ledger fact the console shows comes through this one file, so a
    # future access-control tightening on the simulator's side only ever
    # needs a header added here, not a new browser-facing call site).
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.get(f"/agents/{agent_ref}/daily-summary")
        resp.raise_for_status()
        return resp.json()


def list_agent_transactions(agent_ref: str) -> list[dict]:
    with httpx.Client(base_url=settings.ledger_sim_url, timeout=10.0) as client:
        resp = client.get(f"/agents/{agent_ref}/transactions")
        resp.raise_for_status()
        return resp.json()
