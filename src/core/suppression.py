"""
Determines whether a lead is eligible to be contacted, checking the
suppression_list table. This is the single gatekeeper that MUST be
called before every send — it is deliberately separate from the state
machine so "can we legally/ethically contact this email" is checked
independently of "what stage is this lead at".
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.db.models import SuppressionList, Lead

COOLDOWN_DAYS = 90


def is_suppressed(session: Session, email: str) -> bool:
    """
    Returns True if this email must NOT be contacted — either a
    permanent suppression (unsubscribe/manual/hard-bounce) or a
    still-active cooldown period.
    """
    records = (
        session.query(SuppressionList)
        .filter(SuppressionList.email == email)
        .all()
    )

    for record in records:
        if record.permanent:
            return True
        # Non-permanent (cooldown) record: still active if within window
        cooldown_expires = record.added_at + timedelta(days=COOLDOWN_DAYS)
        if datetime.utcnow() < cooldown_expires:
            return True

    return False


def add_suppression(
    session: Session,
    email: str,
    reason: str,
    permanent: bool,
) -> SuppressionList:
    """
    Adds a suppression record. Callers decide `permanent` based on the
    reason — this function does NOT infer it, to avoid a bug silently
    changing compliance behavior (e.g. treating a bounce as permanent
    when it should be a soft/temporary case, or vice versa).

    Expected reason -> permanent mapping (enforced by caller, not here):
        "unsubscribe"   -> True
        "manual"        -> True
        "bounce_hard"   -> True
        (a normal completed campaign cooldown uses this table implicitly
         via email_events + 90-day check, not a suppression row at all —
         see is_eligible_for_recontact below)
    """
    record = SuppressionList(email=email, reason=reason, permanent=permanent)
    session.add(record)
    session.commit()
    return record


def is_eligible_for_recontact(session: Session, lead: Lead) -> bool:
    """
    A lead that COMPLETED a campaign normally (no reply, followups
    exhausted) becomes eligible again after 90 days — UNLESS a permanent
    suppression record exists for their email (checked separately).
    """
    if is_suppressed(session, lead.email):
        return False

    if lead.status != "COMPLETED":
        return False

    # We reuse created_at here as a simple stand-in for "last activity" —
    # in Phase 6's full wiring, this should read the most recent
    # email_events.sent_at for this lead instead. Flagging this as a
    # TODO to revisit once email_events has real data.
    cooldown_expires = lead.created_at + timedelta(days=COOLDOWN_DAYS)
    return datetime.utcnow() >= cooldown_expires


if __name__ == "__main__":
    from src.db.session import SessionLocal, init_db

    init_db()
    session = SessionLocal()

    test_email = "test-suppress@example.com"

    print("Before suppression:", is_suppressed(session, test_email))
    add_suppression(session, test_email, reason="unsubscribe", permanent=True)
    print("After permanent suppression:", is_suppressed(session, test_email))

    session.close()