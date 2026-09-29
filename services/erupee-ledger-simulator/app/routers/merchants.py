from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Merchant
from app.schemas import MerchantIn, MerchantOut
from app.security import require_service_key

router = APIRouter(prefix="/merchants", tags=["merchants"], dependencies=[Depends(require_service_key)])


@router.post("", response_model=MerchantOut, status_code=201)
def onboard_merchant(payload: MerchantIn, db: Session = Depends(get_db)):
    if db.query(Merchant).filter(Merchant.merchant_ref == payload.merchant_ref).first():
        raise HTTPException(409, "Merchant already onboarded")
    merchant = Merchant(merchant_ref=payload.merchant_ref, name=payload.name, category=payload.category)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("", response_model=list[MerchantOut])
def list_merchants(db: Session = Depends(get_db)):
    return db.query(Merchant).order_by(Merchant.created_at.desc()).all()
