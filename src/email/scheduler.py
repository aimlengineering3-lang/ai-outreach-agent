"""
Determines which QUEUED/NO_REPLY leads are due for their next email
action (initial send or followup), based on configurable delays.

Pure deterministic logic — no LLM. Timing rules are business rules,
not language-understanding tasks.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Lead, Campaign, EmailEvent
from src.core.suppression import is_suppressed


@dataclass
class ScheduledAction:
    lead_id: int
    action_type: str  # "SENT" / "FOLLOWUP1" / "FOLLOWUP2"


def get_due_actions(session: Session, campaign: Campaign) -> list[ScheduledAction]:
    """
    Returns leads in this campaign that are due for their next email
    action right now, based on the campaign's configured follow-up
    delays. Suppressed leads are excluded here — this is the second
    gatekeeper (state machine allows the transition, but suppression.py
    has final veto on every actual send).
    """
    due: list[ScheduledAction] = []

    leads = (
        session.query(Lead)
        .filter(Lead.status.in_(["QUEUED", "CONTACTED", "NO_REPLY"]))
        .all()
    )

    for lead in leads:
        if not lead.email or is_suppressed(session, lead.email):
            continue

        if lead.status == "QUEUED":
            # Never contacted yet for this campaign -> due immediately
            due.append(ScheduledAction(lead_id=lead.id, action_type="SENT"))
            continue

        # lead.status is CONTACTED (awaiting followup_1) or NO_REPLY
        # (followup_1 sent, awaiting followup_2) -> check how long since
        # last event to decide whether followup_1 or followup_2 is due.
        last_event = (
            session.query(EmailEvent)
            .filter(EmailEvent.lead_id == lead.id, EmailEvent.campaign_id == campaign.id)
            .order_by(EmailEvent.sent_at.desc())
            .first()
        )
        if last_event is None or last_event.sent_at is None:
            continue  # no prior send recorded — shouldn't happen, skip defensively

        days_since_last = (datetime.utcnow() - last_event.sent_at).days

        if last_event.event_type == "SENT" and days_since_last >= campaign.followup1_delay_days:
            due.append(ScheduledAction(lead_id=lead.id, action_type="FOLLOWUP1"))
        elif last_event.event_type == "FOLLOWUP1" and days_since_last >= campaign.followup2_delay_days:
            due.append(ScheduledAction(lead_id=lead.id, action_type="FOLLOWUP2"))

    return due


if __name__ == "__main__":
    from src.db.session import SessionLocal, init_db

    init_db()
    session = SessionLocal()

    campaign = session.query(Campaign).first()
    if campaign:
        actions = get_due_actions(session, campaign)
        print(f"Due actions for campaign '{campaign.name}':", actions)
    else:
        print("No campaign found — create one first (Phase 1's test_relationships.py made one).")

    session.close()