"""Two independent auth mechanisms in this service, for two different
callers:

1. X-Service-Key (require_service_key below) — sovereignx-core presents
   this on every call; this service is never called directly by a
   browser for these routes.
2. Agent bearer sessions (require_agent_session below) — the Agent App
   (frontend/agent-app) IS a browser-facing client, but only for the
   agent-assisted routes (agents.py's lookup/otp/transact) — it logs in
   as a specific agent and presents that agent's own session token, not
   the service key, which must never reach a frontend bundle."""
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AgentProfile, AgentSession
from app.timeutil import as_utc


def require_service_key(x_service_key: str | None = Header(default=None)):
    if x_service_key != settings.service_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Service-Key")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_agent_session(db: Session, agent: AgentProfile) -> AgentSession:
    session = AgentSession(
        agent_id=agent.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.agent_session_ttl_hours),
    )
    db.add(session)
    db.flush()
    return session


def require_agent_session(
    agent_ref: str,
    x_agent_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentProfile:
    """Validates the token belongs to a non-expired session for THIS
    agent_ref specifically — Ravi Kumar's session token must not work on
    Priya Sharma's URL, even though both are valid, logged-in agents."""
    if not x_agent_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Agent-Token — log in first")
    session = db.query(AgentSession).filter(AgentSession.id == x_agent_token).first()
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session — log in again")
    if datetime.now(timezone.utc) > as_utc(session.expires_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired — log in again")
    agent = db.query(AgentProfile).filter(AgentProfile.id == session.agent_id).first()
    if not agent or agent.agent_ref != agent_ref:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This session does not belong to this agent")
    return agent
