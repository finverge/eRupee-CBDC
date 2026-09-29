import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Enum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "platform_admin"
    SCHEME_ADMINISTRATOR = "scheme_administrator"
    COMPLIANCE_OFFICER = "compliance_officer"
    SPONSOR_BANK_OPERATOR = "sponsor_bank_operator"
    AGENT = "agent"


class SchemeStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class EligibilityStatus(str, enum.Enum):
    PENDING = "pending"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"


class BatchStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    CONFIRMED = "confirmed"
    PARTIALLY_FAILED = "partially_failed"
    FAILED = "failed"


class InstructionStatus(str, enum.Enum):
    QUEUED = "queued"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    SKIPPED_NO_CONSENT = "skipped_no_consent"
    SKIPPED_INELIGIBLE = "skipped_ineligible"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    full_name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Scheme(Base):
    """BRD BR-01 / FSD FR-01–FR-04. eligibility_rules and
    permitted_merchant_categories are the scheme-level programmable rule
    inputs (FSD FR-02) attached to every issuance instruction disbursed
    under this scheme."""
    __tablename__ = "schemes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)
    benefit_amount_paisa: Mapped[int] = mapped_column(Integer)
    validity_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    validity_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    permitted_merchant_categories: Mapped[list] = mapped_column(JSON, default=list)  # [] = no lock
    single_use: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[SchemeStatus] = mapped_column(Enum(SchemeStatus), default=SchemeStatus.DRAFT)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    beneficiaries: Mapped[list["Beneficiary"]] = relationship(back_populates="scheme")
    batches: Mapped[list["DisbursementBatch"]] = relationship(back_populates="scheme")


class Beneficiary(Base):
    """FSD FR-05–FR-08. beneficiary_ref is the tokenised identifier passed
    to the ledger simulator — SovereignX never stores raw KYC/Aadhaar data
    (HLD 6 security note), only this opaque reference plus what the scheme
    needs to operate (name/district for the console UI)."""
    __tablename__ = "beneficiaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scheme_id: Mapped[str] = mapped_column(String, ForeignKey("schemes.id"), index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True, unique=True)
    full_name: Mapped[str] = mapped_column(String)
    district: Mapped[str] = mapped_column(String)
    eligibility_status: Mapped[EligibilityStatus] = mapped_column(Enum(EligibilityStatus), default=EligibilityStatus.PENDING)
    eligibility_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    consent_status: Mapped[ConsentStatus] = mapped_column(Enum(ConsentStatus), default=ConsentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scheme: Mapped["Scheme"] = relationship(back_populates="beneficiaries")
    consent_records: Mapped[list["ConsentRecord"]] = relationship(back_populates="beneficiary")


class ConsentRecord(Base):
    """Simulated ConsentBridge capture (FSD FR-07, FR-19) — a real
    deployment calls the actual ConsentBridge platform's API; this table
    implements the same purpose/status/timestamp contract in-process so
    the rest of this service (disbursement gating) doesn't change when a
    real ConsentBridge integration is wired in."""
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    beneficiary_id: Mapped[str] = mapped_column(String, ForeignKey("beneficiaries.id"), index=True)
    purpose: Mapped[str] = mapped_column(String, default="subsidy_eligibility_verification")
    status: Mapped[ConsentStatus] = mapped_column(Enum(ConsentStatus))
    recorded_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    beneficiary: Mapped["Beneficiary"] = relationship(back_populates="consent_records")


class DisbursementBatch(Base):
    """FSD FR-09–FR-12. One admin-triggered disbursement run for a scheme
    (optionally scoped to a district) — the Disbursement Orchestration
    Agent builds one IssuanceInstruction per eligible+consented
    beneficiary and submits each to the ledger simulator."""
    __tablename__ = "disbursement_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    scheme_id: Mapped[str] = mapped_column(String, ForeignKey("schemes.id"), index=True)
    district: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[BatchStatus] = mapped_column(Enum(BatchStatus), default=BatchStatus.QUEUED)
    beneficiary_count: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_amount_paisa: Mapped[int] = mapped_column(Integer, default=0)
    triggered_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scheme: Mapped["Scheme"] = relationship(back_populates="batches")
    instructions: Mapped[list["IssuanceInstruction"]] = relationship(back_populates="batch")


class IssuanceInstruction(Base):
    """Core's own record of an instruction it submitted to the ledger
    simulator — external_instruction_id is the id the simulator echoes
    back (FSD FR-11 status tracking, retry-with-backoff)."""
    __tablename__ = "issuance_instructions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    external_instruction_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    batch_id: Mapped[str] = mapped_column(String, ForeignKey("disbursement_batches.id"), index=True)
    beneficiary_id: Mapped[str] = mapped_column(String, ForeignKey("beneficiaries.id"), index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    amount_paisa: Mapped[int] = mapped_column(Integer)
    status: Mapped[InstructionStatus] = mapped_column(Enum(InstructionStatus), default=InstructionStatus.QUEUED)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["DisbursementBatch"] = relationship(back_populates="instructions")
    reconciliation: Mapped["ReconciliationRecord"] = relationship(back_populates="instruction", uselist=False)


class ReconciliationRecord(Base):
    """FSD FR-13–FR-14. Created by the Reconciliation Agent
    (app/services/reconciliation.py) when it pulls a redemption event from
    the ledger simulator and matches it to the instruction that funded it."""
    __tablename__ = "reconciliation_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    instruction_id: Mapped[str] = mapped_column(String, ForeignKey("issuance_instructions.id"), index=True)
    external_redemption_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    merchant_ref: Mapped[str] = mapped_column(String)
    merchant_category: Mapped[str] = mapped_column(String)
    amount_paisa: Mapped[int] = mapped_column(Integer)
    match_status: Mapped[str] = mapped_column(String)  # "matched" | "blocked"
    rule_check_result: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    instruction: Mapped["IssuanceInstruction"] = relationship(back_populates="reconciliation")


class ComplianceAlert(Base):
    """Simulated Fraud360/AML360 CBDC rule pack output (FSD FR-16–FR-18).
    See app/services/compliance.py for the actual rule logic — a real
    rule pack lives in the real Fraud360/AML360 products; this is an
    honest, working simulation of their contract, not a fabricated
    connection to them."""
    __tablename__ = "compliance_alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String)  # "Fraud360" | "AML360"
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    rule_triggered: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN)
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentDailyReconciliation(Base):
    """FSD FR-31 — "reconciled against the sponsor bank's settlement to
    that agent on a daily cycle." erupee-ledger-simulator computes the
    day's activity live from its own AssistedTransaction table
    (GET /agents/{ref}/daily-summary) but keeps no history of past days;
    THIS table is that history, pulled and durably recorded here by
    reconciliation.py's /reconciliation/run — the same run that pulls
    redemption events also pulls one summary per active agent. One row
    per (agent_ref, date): re-running reconciliation later the same day
    updates the existing row (an upsert, not a new row), since the
    "day's total so far" is still evolving until the day ends."""
    __tablename__ = "agent_daily_reconciliations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_ref: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String, index=True)  # YYYY-MM-DD, matches the simulator's own summary date field
    transaction_count: Mapped[int] = mapped_column(Integer)
    total_amount_paisa: Mapped[int] = mapped_column(Integer)
    daily_limit_paisa: Mapped[int] = mapped_column(Integer)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
