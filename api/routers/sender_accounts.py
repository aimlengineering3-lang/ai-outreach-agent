from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db.models import SenderAccount
from src.email.health_monitor import compute_capacity
from api.deps import get_db
from api.schemas import SenderAccountOut, SenderAccountCreate, SenderAccountUpdate

router = APIRouter(prefix="/sender-accounts", tags=["sender-accounts"])


@router.get("", response_model=list[SenderAccountOut])
def list_sender_accounts(db: Session = Depends(get_db)):
    accounts = db.query(SenderAccount).all()
    out = []
    for acc in accounts:
        cap = compute_capacity(db, acc)
        out.append(
            SenderAccountOut(
                id=acc.id, email=acc.email, provider=acc.provider,
                daily_limit=acc.daily_limit, sent_today=acc.sent_today,
                bounce_count_7d=acc.bounce_count_7d,
                spam_complaint_count_7d=acc.spam_complaint_count_7d,
                status=cap.recommended_status,
                available_capacity=cap.available_capacity,
                capacity_reason=cap.reason,
            )
        )
    db.commit()  # persist any daily reset compute_capacity() just applied
    return out


@router.post("", response_model=SenderAccountOut)
def create_sender_account(payload: SenderAccountCreate, db: Session = Depends(get_db)):
    if not payload.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    account = SenderAccount(email=payload.email.strip(), provider=payload.provider, daily_limit=payload.daily_limit)
    db.add(account)
    db.commit()
    db.refresh(account)
    cap = compute_capacity(db, account)
    db.commit()
    return SenderAccountOut(
        id=account.id, email=account.email, provider=account.provider,
        daily_limit=account.daily_limit, sent_today=account.sent_today,
        bounce_count_7d=account.bounce_count_7d, spam_complaint_count_7d=account.spam_complaint_count_7d,
        status=cap.recommended_status, available_capacity=cap.available_capacity, capacity_reason=cap.reason,
    )


@router.patch("/{account_id}", response_model=SenderAccountOut)
def update_sender_account(account_id: int, payload: SenderAccountUpdate, db: Session = Depends(get_db)):
    account = db.query(SenderAccount).filter(SenderAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Sender account not found")
    account.daily_limit = payload.daily_limit
    db.commit()
    db.refresh(account)
    cap = compute_capacity(db, account)
    db.commit()
    return SenderAccountOut(
        id=account.id, email=account.email, provider=account.provider,
        daily_limit=account.daily_limit, sent_today=account.sent_today,
        bounce_count_7d=account.bounce_count_7d, spam_complaint_count_7d=account.spam_complaint_count_7d,
        status=cap.recommended_status, available_capacity=cap.available_capacity, capacity_reason=cap.reason,
    )
