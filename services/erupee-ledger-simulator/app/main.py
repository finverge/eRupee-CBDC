"""
e-Rupee Ledger Simulator — stands in for a Sponsor Bank / NBFC's core
banking system + its connectivity to RBI's CBDC ledger.

⚠️ SIMULATOR, NOT A REAL INTEGRATION. See app/config.py's module docstring
for why this exists and what it does and doesn't prove.

Run locally:
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8401

Then: http://localhost:8401/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.routers import wallets, issuance, merchants, redemption, public_wallet, agents, ussd, offline
from app.seed import seed_demo_data
from app.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    description="SIMULATOR for a Sponsor Bank / NBFC's e₹ ledger. Not a real RBI or bank integration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev-grade — see sovereignx-core/app/main.py for the same note
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wallets.router)
app.include_router(issuance.router)
app.include_router(merchants.router)
app.include_router(redemption.router)
app.include_router(public_wallet.router)
app.include_router(agents.router)
app.include_router(ussd.router)
app.include_router(offline.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "simulated_sponsor_bank": settings.sponsor_bank_name,
        "note": "This is a simulator. It does not connect to RBI or any real bank.",
    }
