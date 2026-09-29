from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models import (
    UserRole, SchemeStatus, EligibilityStatus, ConsentStatus, BatchStatus,
    InstructionStatus, AlertStatus,
)


# ---------- Auth ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    role: UserRole
    full_name: str


class MeOut(BaseModel):
    id: str
    email: str
    role: UserRole
    full_name: str

    class Config:
        from_attributes = True


# ---------- Schemes ----------
class SchemeCreate(BaseModel):
    name: str
    department: str
    benefit_amount_paisa: int = Field(gt=0)
    validity_start: datetime
    validity_end: datetime
    permitted_merchant_categories: list[str] = []
    single_use: bool = False


class SchemeOut(BaseModel):
    id: str
    name: str
    department: str
    benefit_amount_paisa: int
    validity_start: datetime
    validity_end: datetime
    permitted_merchant_categories: list[str]
    single_use: bool
    status: SchemeStatus
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class SchemeStatusUpdate(BaseModel):
    status: SchemeStatus


# ---------- Beneficiaries ----------
class BeneficiaryIngestItem(BaseModel):
    beneficiary_ref: str
    full_name: str
    district: str


class BeneficiaryIngestRequest(BaseModel):
    items: list[BeneficiaryIngestItem]


class BeneficiaryOut(BaseModel):
    id: str
    scheme_id: str
    beneficiary_ref: str
    full_name: str
    district: str
    eligibility_status: EligibilityStatus
    eligibility_reason: str | None
    consent_status: ConsentStatus
    created_at: datetime

    class Config:
        from_attributes = True


class ConsentAction(BaseModel):
    action: str  # "grant" | "withdraw"


# ---------- Disbursements ----------
class DisbursementBatchCreate(BaseModel):
    scheme_id: str
    district: str | None = None


class DisbursementBatchOut(BaseModel):
    id: str
    scheme_id: str
    district: str | None
    status: BatchStatus
    beneficiary_count: int
    confirmed_count: int
    failed_count: int
    total_amount_paisa: int
    triggered_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class IssuanceInstructionOut(BaseModel):
    id: str
    external_instruction_id: str
    beneficiary_ref: str
    amount_paisa: int
    status: InstructionStatus
    failure_reason: str | None
    created_at: datetime
    confirmed_at: datetime | None

    class Config:
        from_attributes = True


# ---------- Reconciliation / Compliance ----------
class ReconciliationRecordOut(BaseModel):
    id: str
    instruction_id: str
    external_redemption_id: str
    merchant_ref: str
    merchant_category: str
    amount_paisa: int
    match_status: str
    rule_check_result: str
    created_at: datetime

    class Config:
        from_attributes = True


class ComplianceAlertOut(BaseModel):
    id: str
    source: str
    beneficiary_ref: str
    rule_triggered: str
    detail: str
    status: AlertStatus
    reviewed_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertReviewAction(BaseModel):
    action: str  # "review" | "dismiss"


class ReconciliationRunResult(BaseModel):
    pulled: int
    matched: int
    blocked: int
    new_alerts: int
    agent_summaries_pulled: int


class AgentDailyReconciliationOut(BaseModel):
    id: str
    agent_ref: str
    date: str
    transaction_count: int
    total_amount_paisa: int
    daily_limit_paisa: int
    pulled_at: datetime

    class Config:
        from_attributes = True


# ---------- Dashboard ----------
class FunnelOut(BaseModel):
    eligible: int
    disbursed: int
    redeemed: int
    flagged: int


class DashboardOut(BaseModel):
    beneficiaries_onboarded: int
    total_disbursed_paisa: int
    total_redeemed_paisa: int
    redemption_rate_pct: float
    open_alerts: int
    funnel: FunnelOut
    recent_batches: list[DisbursementBatchOut]
    open_alert_list: list[ComplianceAlertOut]


# ---------- Agents (proxied to erupee-ledger-simulator — FSD FR-29–FR-32) ----------
class AgentCreate(BaseModel):
    agent_ref: str
    name: str
    assigned_region: str
    daily_limit_paisa: int = Field(gt=0, default=5000000)
    password: str = Field(min_length=6)  # the agent's own login for the Agent App — never stored here, passed straight through to the ledger simulator


class AgentOut(BaseModel):
    id: str
    agent_ref: str
    name: str
    assigned_region: str
    daily_limit_paisa: int
    kyc_status: str
    created_at: datetime


class AgentDailySummaryOut(BaseModel):
    agent_ref: str
    date: str
    transaction_count: int
    total_amount_paisa: int
    daily_limit_paisa: int
    remaining_paisa: int


class AgentTransactionOut(BaseModel):
    id: str
    agent_ref: str
    beneficiary_ref: str
    action: str
    amount_paisa: int | None
    merchant_ref: str | None
    rule_check_result: str | None
    executed: bool
    created_at: datetime
