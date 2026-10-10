"""
Determines which QUEUED/NO_REPLY leads are due for their next email
action (initial send or followup), based on configurable delays.

Pure deterministic logic — no LLM. Timing rules are business rules,
not language-understanding tasks.

Performance note: this bulk-loads suppression and event data upfront
instead of querying per-lead, since per-lead queries become extremely
slow against a networked (Supabase) database once lead counts grow.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, load_only

from src.db.models import Lead, Campaign, EmailEvent, SuppressionList


@dataclass
class ScheduledAction:
    lead_id: int
    action_type: str  # "SENT" / "FOLLOWUP1" / "FOLLOWUP2"


def get_due_actions(session: Session, campaign: Campaign) -> list[ScheduledAction]:
    """
    Returns leads in this campaign that are due for their next email
    action right now, based on the campaign's configured follow-up
    delays.
    """
    due: list[ScheduledAction] = []

    leads = (
        session.query(Lead)
        .options(load_only(Lead.id, Lead.email, Lead.status, Lead.created_at))
        .filter(
            Lead.status.in_(["QUEUED", "CONTACTED", "NO_REPLY"]),
            Lead.niche == campaign.niche,
        )
        .order_by(Lead.created_at.asc())
        .all()
    )
    if not leads:
        return due

    lead_ids = [lead.id for lead in leads]
    lead_emails = {lead.email for lead in leads if lead.email}

    # Bulk-load suppression records for all relevant emails in one query,
    # instead of one query per lead.
    suppressed_emails = set()
    if lead_emails:
        suppressed_rows = (
            session.query(SuppressionList)
            .filter(SuppressionList.email.in_(lead_emails))
            .all()
        )
        for row in suppressed_rows:
            if row.permanent:
                suppressed_emails.add(row.email)
            else:
                from datetime import timedelta
                cooldown_expires = row.added_at + timedelta(days=90)
                if datetime.utcnow() < cooldown_expires:
                    suppressed_emails.add(row.email)

    # Bulk-load the most recent EmailEvent per lead in one query, instead
    # of one query per lead.
    all_events = (
        session.query(EmailEvent)
        .options(load_only(EmailEvent.id, EmailEvent.lead_id, EmailEvent.event_type, EmailEvent.sent_at))
        .filter(EmailEvent.lead_id.in_(lead_ids), EmailEvent.campaign_id == campaign.id)
        .order_by(EmailEvent.sent_at.desc())
        .all()
    )
    latest_event_by_lead = {}
    for event in all_events:
        if event.lead_id not in latest_event_by_lead:
            latest_event_by_lead[event.lead_id] = event

    for lead in leads:
        if not lead.email or lead.email in suppressed_emails:
            continue

        if lead.status == "QUEUED":
            due.append(ScheduledAction(lead_id=lead.id, action_type="SENT"))
            continue

        last_event = latest_event_by_lead.get(lead.id)
        if last_event is None or last_event.sent_at is None:
            continue

        days_since_last = (datetime.utcnow() - last_event.sent_at).days

        if last_event.event_type == "SENT" and days_since_last >= campaign.followup1_delay_days:
            due.append(ScheduledAction(lead_id=lead.id, action_type="FOLLOWUP1"))
        elif (
            last_event.event_type == "FOLLOWUP1"
            and campaign.followup2_enabled
            and days_since_last >= campaign.followup2_delay_days
        ):
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