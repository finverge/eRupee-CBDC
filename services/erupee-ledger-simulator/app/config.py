"""Settings for the e-Rupee Ledger Simulator.

⚠️ THIS SERVICE IS A SIMULATOR, NOT A REAL RBI/BANK INTEGRATION. ⚠️
There is no real connectivity to RBI's CBDC ledger or to any actual sponsor
bank's core banking system — neither exists for this codebase to connect to.
This service stands in for the "Sponsor Bank / NBFC — Core Banking + e₹ CBDC
Ledger Access" box in the HLD (Section 3/4) and implements the same contract
a real SovereignX e₹ Connector Adapter would call (HLD Section 4.3: submit
issuance batch, query status, receive redemption events) so that swapping
this out for a real bank integration later is a config change (a different
base URL + real auth) in sovereignx-core, not a rewrite of its callers.

Every response this service returns should be read as "what a real sponsor
bank's ledger would plausibly return," not as a real financial record.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ERUPEE_LEDGER_SIM_", env_file=".env", extra="ignore")

    app_name: str = "e-Rupee Ledger Simulator (Sponsor Bank + RBI CBDC Ledger stand-in)"
    port: int = 8401

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/erupee_ledger_simulator"

    # Shared secret sovereignx-core must present (X-Service-Key header) —
    # this service is never called directly by a browser.
    service_api_key: str = "dev-erupee-ledger-sim-key"

    sponsor_bank_name: str = "DemoBank NBFC (Simulated Sponsor Bank)"
    sponsor_bank_code: str = "DEMO"

    # Agent App login sessions (agents.py) — separate from the per-
    # transaction OtpChallenge TTL (agents.py's own OTP_TTL_MINUTES).
    agent_session_ttl_hours: int = 8

    # USSD PIN brute-force lockout (ussd.py) — 3 wrong PINs within any
    # window locks the beneficiary out for 15 minutes, reset on the next
    # correct PIN. Deliberately short for a demo; a real deployment would
    # tune this against its own fraud-ops guidance, not this default.
    ussd_pin_max_attempts: int = 3
    ussd_pin_lockout_minutes: int = 15


settings = Settings()
