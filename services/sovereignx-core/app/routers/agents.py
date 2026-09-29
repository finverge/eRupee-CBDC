"""Console-facing view onto the agent-assisted channel (FSD FR-29–FR-32).
Onboarding and transacting happen through the Agent App directly against
erupee-ledger-simulator (that app has its own dual-factor OTP flow to
drive) — this router exists so the Scheme Administrator Console can list
agents, onboard new ones, and pull the daily settlement summary each
agent needs reconciled against (FR-31), without embedding the ledger
simulator's service key in the browser. See app/services/ledger_client.py
for why every call here is a proxy, not a database query of its own —
sovereignx-core keeps no local copy of agent data; the ledger simulator
is the one source of truth for it, same as it is for wallets."""
from fastapi import APIRouter, Depends, HTTPException
import httpx

from app.models import User, UserRole
from app.schemas import AgentCreate, AgentOut, AgentDailySummaryOut, AgentTransactionOut
from app.security import get_current_user, require_roles
from app.services import ledger_client

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentOut, status_code=201,
             dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.PLATFORM_ADMIN))])
def onboard_agent(payload: AgentCreate):
    try:
        return ledger_client.onboard_agent(payload.agent_ref, payload.name, payload.assigned_region, payload.daily_limit_paisa, payload.password)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.json().get("detail", "Could not onboard agent"))


@router.get("", response_model=list[AgentOut])
def list_agents(_user: User = Depends(get_current_user)):
    return ledger_client.list_agents()


@router.get("/{agent_ref}/daily-summary", response_model=AgentDailySummaryOut)
def agent_daily_summary(agent_ref: str, _user: User = Depends(get_current_user)):
    try:
        return ledger_client.get_agent_daily_summary(agent_ref)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.json().get("detail", "Agent not found"))


@router.get("/{agent_ref}/transactions", response_model=list[AgentTransactionOut])
def agent_transactions(agent_ref: str, _user: User = Depends(get_current_user)):
    try:
        return ledger_client.list_agent_transactions(agent_ref)
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.json().get("detail", "Agent not found"))
