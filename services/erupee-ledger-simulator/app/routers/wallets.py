from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Wallet
from app.schemas import WalletOut
from app.security import require_service_key

router = APIRouter(prefix="/wallets", tags=["wallets"], dependencies=[Depends(require_service_key)])


@router.get("/{beneficiary_ref}", response_model=WalletOut)
def get_wallet(beneficiary_ref: str, db: Session = Depends(get_db)):
    wallet = db.query(Wallet).filter(Wallet.beneficiary_ref == beneficiary_ref).first()
    if not wallet:
        raise HTTPException(404, "No wallet for this beneficiary — none issued to them yet")
    return wallet


@router.get("", response_model=list[WalletOut])
def list_wallets(db: Session = Depends(get_db)):
    return db.query(Wallet).order_by(Wallet.created_at.desc()).all()
