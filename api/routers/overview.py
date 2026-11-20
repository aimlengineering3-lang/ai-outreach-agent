from datetime import datetime, date
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Lead, EmailEvent, SuppressionList, SenderAccount, Campaign
from src.email.health_monitor import compute_capacity
from src.email.scheduler import get_due_actions
from api.deps import get_db
from api.schemas import OverviewStats, ForecastStats

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=OverviewStats)
def get_overview(db: Session = Depends(get_db)):
    total_leads = db.query(Lead).count()
    researched = db.query(Lead).filter(Lead.status != "NEW").count()

    today_start = datetime.combine(date.today(), datetime.min.time())
    sent_today = (
        db.query(EmailEvent)
        .filter(EmailEvent.event_type == "SENT", EmailEvent.sent_at >= today_start)
        .count()
    )
    replies = db.query(EmailEvent).filter(EmailEvent.event_type == "REPLY").count()
    suppressed = db.query(SuppressionList).count()

    reply_events = db.query(EmailEvent).filter(EmailEvent.event_type == "REPLY").all()
    reply_categories: dict[str, int] = {}
    for e in reply_events:
        if e.notes and "category=" in e.notes:
            cat = e.notes.split("category=")[1].strip()
            reply_categories[cat] = reply_categories.get(cat, 0) + 1

    active_accounts = db.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    for acc in active_accounts:
        compute_capacity(db, acc)
    db.commit()
    total_daily_capacity = sum(acc.daily_limit for acc in active_accounts)

    status_counts = dict(db.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all())

    return OverviewStats(
        total_leads=total_leads, researched=researched, sent_today=sent_today,
        total_daily_capacity=total_daily_capacity, replies=replies, suppressed=suppressed,
        status_counts=status_counts, reply_categories=reply_categories,
    )


@router.get("/forecast", response_model=ForecastStats)
def get_forecast(db: Session = Depends(get_db)):
    all_campaigns = db.query(Campaign).filter(Campaign.status == "ACTIVE").all()
    total_followups_due = 0
    for c in all_campaigns:
        due = get_due_actions(db, c)
        total_followups_due += sum(1 for a in due if a.action_type in ("FOLLOWUP1", "FOLLOWUP2"))

    active_accounts = db.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    # Same logic as the old dashboard: compute_capacity() applies the daily
    # reset AND the throttle (a throttled account only has half its limit),
    # so we use its available_capacity instead of daily_limit - sent_today.
    capacities = [compute_capacity(db, acc) for acc in active_accounts]
    remaining_today = sum(c.available_capacity for c in capacities)
    total_capacity = sum(acc.daily_limit for acc in active_accounts)
    already_sent = sum(acc.sent_today for acc in active_accounts)
    db.commit()  # compute_capacity() may have just applied a daily reset
    room_for_new_leads = max(0, remaining_today - total_followups_due)

    today_start = datetime.combine(date.today(), datetime.min.time())
    emails_found_today = (
        db.query(Lead).filter(Lead.email.isnot(None), Lead.created_at >= today_start).count()
    )
    pending_unsent = db.query(Lead).filter(Lead.status == "QUEUED").count()
    needs_manual_review = (
        db.query(Lead).filter(Lead.status == "RESEARCHED", Lead.email.isnot(None)).count()
    )

    return ForecastStats(
        emails_found_today=emails_found_today, pending_unsent=pending_unsent,
        followups_due_today=total_followups_due, remaining_capacity_today=remaining_today,
        room_for_new_leads=room_for_new_leads, needs_manual_review=needs_manual_review,
        total_capacity_today=total_capacity, already_sent_today=already_sent,
    )
