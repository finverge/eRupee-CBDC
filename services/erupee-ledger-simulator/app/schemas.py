from datetime import datetime

from pydantic import BaseModel, Field

from app.models import InstructionStatus, RuleCheckResult


class ProgrammableRules(BaseModel):
    expires_at: datetime | None = None
    merchant_categories: list[str] | None = None  # None = no lock, any category accepted
    geo_fence: str | None = None
    single_use: bool = False


class IssuanceRequest(BaseModel):
    external_instruction_id: str
    beneficiary_ref: str
    amount_paisa: int = Field(gt=0)
    scheme_ref: str | None = None
    rules: ProgrammableRules = ProgrammableRules()


class IssuanceOut(BaseModel):
    id: str
    external_instruction_id: str
    beneficiary_ref: str
    amount_paisa: int
    status: InstructionStatus
    failure_reason: str | None
    rules: dict
    scheme_ref: str | None
    created_at: datetime
    confirmed_at: datetime | None

    class Config:
        from_attributes = True


class WalletOut(BaseModel):
    id: str
    beneficiary_ref: str
    balance_paisa: int
    created_at: datetime

    class Config:
        from_attributes = True


class MerchantIn(BaseModel):
    merchant_ref: str
    name: str
    category: str


class MerchantOut(BaseModel):
    id: str
    merchant_ref: str
    name: str
    category: str
    kyb_status: str
    settlement_balance_paisa: int
    created_at: datetime

    class Config:
        from_attributes = True


class RedemptionRequest(BaseModel):
    beneficiary_ref: str
    merchant_ref: str
    amount_paisa: int = Field(gt=0)


class RedemptionOut(BaseModel):
    id: str
    beneficiary_ref: str
    instruction_id: str | None
    merchant_ref: str
    merchant_category: str
    amount_paisa: int
    rule_check_result: RuleCheckResult
    executed: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Agent-assisted channel ----------
class AgentIn(BaseModel):
    agent_ref: str
    name: str
    assigned_region: str
    daily_limit_paisa: int = 5000000
    password: str = Field(min_length=6)


class AgentOut(BaseModel):
    id: str
    agent_ref: str
    name: str
    assigned_region: str
    daily_limit_paisa: int
    kyc_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AgentLoginIn(BaseModel):
    password: str


class AgentLoginOut(BaseModel):
    agent_ref: str
    name: str
    token: str
    expires_at: datetime


class OtpRequestIn(BaseModel):
    beneficiary_ref: str


class OtpRequestOut(BaseModel):
    challenge_id: str
    simulated_code: str  # NEVER do this in a real system — see OtpChallenge's docstring
    expires_at: datetime


class OtpVerifyIn(BaseModel):
    challenge_id: str
    code: str


class OtpVerifyOut(BaseModel):
    verified: bool
    assisted_session_token: str | None = None


class AssistedBalanceOut(BaseModel):
    beneficiary_ref: str
    balance_paisa: int
    bank_name: str  # FSD 9.6 — every assisted screen must show the beneficiary's own bank, not the agent's app brand


class AssistedTransactRequest(BaseModel):
    beneficiary_ref: str
    action: str  # "withdrawal" | "redemption"
    amount_paisa: int = Field(gt=0)
    merchant_ref: str | None = None  # required for "redemption"; ignored for "withdrawal" (uses agent's own cash-out ref)
    assisted_session_token: str


class AssistedTransactionOut(BaseModel):
    id: str
    agent_ref: str
    beneficiary_ref: str
    action: str
    amount_paisa: int | None
    merchant_ref: str | None
    rule_check_result: str | None
    executed: bool
    created_at: datetime


class AgentDailySummaryOut(BaseModel):
    agent_ref: str
    date: str
    transaction_count: int
    total_amount_paisa: int
    daily_limit_paisa: int
    remaining_paisa: int


# ---------- USSD channel ----------
class UssdSessionOut(BaseModel):
    session_id: str
    screen_text: str
    awaiting_input: bool
    session_ended: bool


class UssdInputIn(BaseModel):
    input: str


# ---------- Offline queue ----------
class DeviceRegisterIn(BaseModel):
    device_id: str
    beneficiary_ref: str


class DeviceRegisterOut(BaseModel):
    device_id: str
    beneficiary_ref: str
    daily_cap_paisa: int
    daily_cap_count: int
    device_secret: str  # returned once at registration, same as any device-bootstrap secret


class QueuedTransaction(BaseModel):
    client_tx_id: str
    merchant_ref: str
    amount_paisa: int = Field(gt=0)
    # Kept as the RAW string the device signed, not `datetime` — a
    # Pydantic-parsed-then-reserialized datetime does not always
    # round-trip to the identical string (JS's toISOString() 'Z' /
    # 3-digit ms vs Python's isoformat() '+00:00' / 6-digit us), which
    # would silently break every signature. Parsed into a real datetime
    # only at the one place that writes it to a DB column (offline.py).
    queued_at: str
    signature: str  # HMAC-SHA256(device_secret, f"{client_tx_id}|{merchant_ref}|{amount_paisa}|{queued_at}")


class OfflineSyncIn(BaseModel):
    device_id: str
    transactions: list[QueuedTransaction]


class OfflineSyncResultItem(BaseModel):
    client_tx_id: str
    outcome: str
    executed: bool


class OfflineSyncOut(BaseModel):
    results: list[OfflineSyncResultItem]
