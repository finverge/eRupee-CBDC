from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Scheme, User, UserRole
from app.schemas import SchemeCreate, SchemeOut, SchemeStatusUpdate
from app.security import get_current_user, require_roles

router = APIRouter(prefix="/schemes", tags=["schemes"])


@router.post("", response_model=SchemeOut, status_code=201,
             dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.PLATFORM_ADMIN))])
def create_scheme(payload: SchemeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scheme = Scheme(**payload.model_dump(), created_by=user.full_name)
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.get("", response_model=list[SchemeOut])
def list_schemes(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Scheme).order_by(Scheme.created_at.desc()).all()


@router.get("/{scheme_id}", response_model=SchemeOut)
def get_scheme(scheme_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        from fastapi import HTTPException
        raise HTTPException(404, "Scheme not found")
    return scheme


@router.patch("/{scheme_id}/status", response_model=SchemeOut,
              dependencies=[Depends(require_roles(UserRole.SCHEME_ADMINISTRATOR, UserRole.PLATFORM_ADMIN))])
def update_scheme_status(scheme_id: str, payload: SchemeStatusUpdate, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(404, "Scheme not found")
    scheme.status = payload.status
    db.commit()
    db.refresh(scheme)
    return scheme
