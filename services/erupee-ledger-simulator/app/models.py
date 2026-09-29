"""Simulated sponsor-bank ledger tables. Amounts are stored in paisa
(integer) throughout — never float — same convention as every other
Finverge money-handling service in this ecosystem."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InstructionStatus(str, enum.Enum):
    QUEUED = "queued"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class RuleCheckResult(str, enum.Enum):
    ALLOWED = "allowed"
    BLOCKED_EXPIRED = "blocked_expired"
    BLOCKED_MERCHANT_CATEGORY = "blocked_merchant_category"
    BLOCKED_INSUFFICIENT_BALANCE = "blocked_insufficient_balance"
    BLOCKED_GEO_FENCE = "blocked_geo_fence"
    BLOCKED_SINGLE_USE = "blocked_single_use"


class Wallet(Base):
    """A beneficiary's simulated e₹ wallet at the sponsor bank. Created
    lazily on first issuance to that beneficiary_ref — mirrors how a real
    bank provisions a CBDC wallet against an existing KYC'd account rather
    than SovereignX creating one independently (FSD FR-24)."""
    __tablename__ = "wallets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    beneficiary_ref: Mapped[str] = mapped_column(String, unique=True, index=True)
    balance_paisa: Mapped[int] = mapped_column(Integer, default=0)
    # USSD PIN (FR-33) — defaults to "1234" on creation for this simulator;
    # a real deployment sets this via the sponsor bank's own PIN-setup
    # flow, never a hardcoded default. Stored in the clear here because
    # this is a 4-digit demo PIN in a local simulator, not a production
    # credential store — do not carry this pattern into anything real.
    ussd_pin: Mapped[str] = mapped_column(String, default="1234")
    # USSD brute-force protection (closes the "USSD Simulator has no auth
    # of its own" gap — the PIN itself always was the auth; this is what
    # was missing around it). Tracked per-beneficiary, not per-session,
    # since a session already ends on the first wrong PIN (ussd.py) —
    # nothing stops someone from just dialing again immediately otherwise.
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    instructions: Mapped[list["IssuanceInstruction"]] = relationship(back_populates="wallet")
    redemptions: Mapped[list["RedemptionEvent"]] = relationship(back_populates="wallet")


class IssuanceInstruction(Base):
    """One disbursement instruction submitted by SovereignX (sovereignx-core)
    and executed here against the simulated ledger — HLD 4.3 "Outbound:
    submit issuance instruction batch (with attached programmable rule
    set)". external_instruction_id is sovereignx-core's own id, so both
    sides can correlate without this service exposing its internal id."""
    __tablename__ = "issuance_instructions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    external_instruction_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    wallet_id: Mapped[str] = mapped_column(String, ForeignKey("wallets.id"))
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    amount_paisa: Mapped[int] = mapped_column(Integer)
    status: Mapped[InstructionStatus] = mapped_column(Enum(InstructionStatus), default=InstructionStatus.QUEUED)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    # Programmable rule set attached to THIS issuance (FSD FR-02, FR-12) —
    # stored as JSON since it's read back whole, never queried by field.
    # Shape: {"expires_at": iso8601|null, "merchant_categories": [str]|null,
    #          "geo_fence": str|null, "single_use": bool}
    rules: Mapped[dict] = mapped_column(JSON, default=dict)

    scheme_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wallet: Mapped["Wallet"] = relationship(back_populates="instructions")


class Merchant(Base):
    """Onboarded merchant (FSD FR-35 KYB) able to accept e₹ QR/POS
    redemptions in the simulator."""
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    merchant_ref: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)  # merchant category code, e.g. "FERTILIZER", "GROCERY", "FUEL"
    kyb_status: Mapped[str] = mapped_column(String, default="verified")
    settlement_balance_paisa: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentProfile(Base):
    """A Banking Correspondent / CSC agent (FSD FR-29–FR-32, HLD Section 9
    Tier 3 "No Phone"). Onboarded once, then used for every assisted
    transaction that agent performs across beneficiaries.

    password_hash gates the AGENT's own identity — separate from, and
    checked before, the OtpChallenge that gates the BENEFICIARY's consent
    to a specific transaction (FR-30). Two factors, two different
    people's credentials: the agent proves who *they* are once per shift
    (login), the beneficiary proves the agent is acting on their behalf
    once per transaction (OTP). Nullable only so the three agents
    onboarded before this field existed keep working without a forced
    migration — every NEW agent gets one at onboarding (agents.py)."""
    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_ref: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    assigned_region: Mapped[str] = mapped_column(String)
    daily_limit_paisa: Mapped[int] = mapped_column(Integer, default=5000000)  # ₹50,000/day default
    kyc_status: Mapped[str] = mapped_column(String, default="verified")
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentSession(Base):
    """An agent's own login session (new — closes the "Agent App has no
    auth of its own" gap). Deliberately NOT a JWT: this service has no
    JWT library dependency and a DB-row-as-token is the same pattern
    OtpChallenge already uses here — one fewer concept to hold in your
    head reading this codebase. The token IS the row id."""
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agent_profiles.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OtpChallenge(Base):
    """Simulates the beneficiary-side factor of dual-factor assisted-
    transaction auth (FR-30) — in a real deployment this rides the
    sponsor bank's existing AePS/biometric rails or an SMS OTP gateway;
    this simulator has neither, so it generates a code and returns it
    directly in the API response, clearly labeled as simulated delivery.
    Never do this in anything that isn't a local dev simulator."""
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agent_profiles.id"), index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    code: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AssistedTransaction(Base):
    """One agent-assisted action (FR-29, FR-32) — balance check needs no
    OTP (low risk, read-only); withdrawal/redemption require a verified
    OtpChallenge, checked against the agent's daily_limit_paisa before
    executing. Reconciled against the sponsor bank's settlement to that
    agent daily (FR-31) via GET /agents/{ref}/daily-summary."""
    __tablename__ = "assisted_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(String, ForeignKey("agent_profiles.id"), index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)  # "balance_check" | "withdrawal" | "redemption"
    amount_paisa: Mapped[int | None] = mapped_column(Integer, nullable=True)
    merchant_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    auth_method: Mapped[str] = mapped_column(String)  # "otp" (only method this simulator implements)
    rule_check_result: Mapped[str | None] = mapped_column(String, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UssdSession(Base):
    """A feature-phone USSD session (FR-33–FR-34). Short-lived, in-memory-
    scale state machine — the session row itself holds only the current
    menu `state` and (after PIN entry) the resolved beneficiary_ref;
    balance/history are never cached here, only fetched live when the
    session actually needs them (FR-34)."""
    __tablename__ = "ussd_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    state: Mapped[str] = mapped_column(String, default="enter_beneficiary_ref")
    beneficiary_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_merchant_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_amount_paisa: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DeviceRegistration(Base):
    """A beneficiary's wallet-SDK-enabled smartphone, registered once so
    its offline queue submissions can be capped per FSD FR-28. daily_cap_*
    reset by comparing against SUM(OfflineQueueSubmission.amount_paisa)
    for that device today, not a separate counter column — avoids a
    counter/actual drift bug."""
    __tablename__ = "device_registrations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    daily_cap_paisa: Mapped[int] = mapped_column(Integer, default=200000)  # ₹2,000/day default offline exposure
    daily_cap_count: Mapped[int] = mapped_column(Integer, default=5)
    device_secret: Mapped[str] = mapped_column(String)  # HMAC key — see offline.py module docstring
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OfflineQueueSubmission(Base):
    """One transaction that was queued on-device while offline and
    submitted later (FR-26–FR-27). client_tx_id is the device-generated
    idempotency key — a replayed sync (e.g. retried after a dropped
    response) must not double-spend."""
    __tablename__ = "offline_queue_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    device_id: Mapped[str] = mapped_column(String, index=True)
    client_tx_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    merchant_ref: Mapped[str] = mapped_column(String)
    amount_paisa: Mapped[int] = mapped_column(Integer)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    outcome: Mapped[str] = mapped_column(String)  # "allowed" | a RuleCheckResult value | "cap_exceeded" | "bad_signature"
    executed: Mapped[bool] = mapped_column(Boolean, default=False)


class RedemptionEvent(Base):
    """A beneficiary spending e₹ at a merchant — HLD 4.3 "Inbound: receive
    redemption event notifications." rule_check_result is BLOCKED_* when
    the instruction's programmable rules reject the spend (still logged,
    money doesn't move) — sovereignx-core's Reconciliation/Fraud agents
    poll GET /redemptions to pick these up (FSD FR-13–FR-14, FR-16)."""
    __tablename__ = "redemption_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    wallet_id: Mapped[str] = mapped_column(String, ForeignKey("wallets.id"))
    beneficiary_ref: Mapped[str] = mapped_column(String, index=True)
    instruction_id: Mapped[str | None] = mapped_column(String, ForeignKey("issuance_instructions.id"), nullable=True)
    merchant_ref: Mapped[str] = mapped_column(String, index=True)
    merchant_category: Mapped[str] = mapped_column(String)
    amount_paisa: Mapped[int] = mapped_column(Integer)
    rule_check_result: Mapped[RuleCheckResult] = mapped_column(Enum(RuleCheckResult))
    executed: Mapped[bool] = mapped_column(Boolean, default=False)  # false when blocked — no balance movement
    pulled_by_core: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # sovereignx-core reconciliation poll cursor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    wallet: Mapped["Wallet"] = relationship(back_populates="redemptions")
