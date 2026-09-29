"""Settings for SovereignX Core — the Subsidy & DBT Orchestration Engine,
Wallet/Merchant Enablement orchestration, compliance and consent modules
(BRD/FSD Release 1). This service never touches e₹ directly — every
ledger-affecting call goes to erupee-ledger-simulator over HTTP, exactly
as HLD Section 4.3 describes the real e₹ Connector Adapter working against
a real sponsor bank. See erupee-ledger-simulator/app/config.py for why
that dependency is a simulator, not a real bank/RBI integration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOVEREIGNX_CORE_", env_file=".env", extra="ignore")

    app_name: str = "Finverge SovereignX Core"
    port: int = 8402

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sovereignx_core"

    ledger_sim_url: str = "http://127.0.0.1:8401"
    ledger_sim_service_key: str = "dev-erupee-ledger-sim-key"

    jwt_secret: str = "dev-sovereignx-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480

    # Fraud360/AML360 CBDC rule pack (simulated in-process — see
    # app/services/compliance.py's module docstring for why this is a
    # real, running rule engine and not a fabricated "connection" to the
    # actual Fraud360/AML360 products, which this service does not have
    # credentials for).
    velocity_window_minutes: int = 5
    velocity_max_attempts: int = 3

    # Background reconciliation loop (FSD FR-31's "daily cycle", made
    # observable in a local dev demo — see main.py's _reconciliation_loop
    # docstring for why 2 minutes here, not a literal 24 hours).
    reconciliation_loop_interval_seconds: int = 120


settings = Settings()
