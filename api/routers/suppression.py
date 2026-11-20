from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.models import SuppressionList
from api.deps import get_db
from api.schemas import SuppressionOut, SuppressionCreate

router = APIRouter(prefix="/suppression", tags=["suppression"])


@router.get("", response_model=list[SuppressionOut])
def list_suppression(db: Session = Depends(get_db)):
    return db.query(SuppressionList).order_by(SuppressionList.added_at.desc()).all()


@router.post("", response_model=SuppressionOut)
def add_suppression(payload: SuppressionCreate, db: Session = Depends(get_db)):
    if not payload.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    record = SuppressionList(
        email=payload.email.strip(), reason=payload.reason, permanent=payload.permanent,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
