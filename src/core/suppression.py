"""
Determines whether a lead is eligible to be contacted, checking the
suppression_list table. This is the single gatekeeper that MUST be
called before every send — it is deliberately separate from the state
machine so "can we legally/ethically contact this email" is checked
independently of "what stage is this lead at".
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import SuppressionList, Lead

COOLDOWN_DAYS = 90


def normalize_email(email: str) -> str:
    """Ek hi standard form: lowercase + trimmed. Suppression hamesha isi form mein compare hoti hai."""
    return (email or "").strip().lower()


def is_suppressed(session: Session, email: str) -> bool:
    """
    Returns True if this email must NOT be contacted — either a
    permanent suppression (unsubscribe/manual/hard-bounce) or a
    still-active cooldown period.

    Matching case-insensitive hai (Info@X.com == info@X.com), aur campaign
    se koi taluq nahi — suppression GLOBAL hai, har campaign pe lagti hai.
    """
    key = normalize_email(email)
    if not key:
        return False

    records = (
        session.query(SuppressionList)
        .filter(func.lower(func.trim(SuppressionList.email)) == key)
        .all()
    )

    for record in records:
        if record.permanent:
            return True
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
    Adds a suppression record (idempotent: agar is email ki permanent
    record pehle se hai to dobara row nahi banti).

    Expected reason -> permanent mapping (enforced by caller):
        "unsubscribe" -> True, "manual" -> True, "bounce_hard" -> True
    """
    key = normalize_email(email)

    if permanent:
        existing = (
            session.query(SuppressionList)
            .filter(func.lower(func.trim(SuppressionList.email)) == key,
                    SuppressionList.permanent.is_(True))
            .first()
        )
        if existing:
            return existing

    record = SuppressionList(email=key, reason=reason, permanent=permanent)
    session.add(record)
    session.commit()
    return record


def suppress_everywhere(session: Session, email: str, reason: str = "bounce_hard") -> int:
    """
    Global kill-switch: email ko permanent suppress karta hai AUR is email
    wale har Lead row (kisi bhi campaign/state ka) ko SUPPRESSED mark karta hai.
    Returns: kitne lead rows update hue.
    """
    key = normalize_email(email)
    if not key:
        return 0

    add_suppression(session, key, reason=reason, permanent=True)

    updated = 0
    leads = session.query(Lead).filter(func.lower(func.trim(Lead.email)) == key).all()
    for lead in leads:
        if lead.status not in ("SUPPRESSED", "REPLIED", "STOPPED"):
            lead.status = "SUPPRESSED"
            updated += 1
    session.commit()
    return updated


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