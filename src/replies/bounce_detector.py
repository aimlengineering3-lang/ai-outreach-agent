"""
Detects bounce notification emails in the inbox (from Gmail's own
"Mail Delivery Subsystem"), matches them back to the lead whose email
bounced, marks that lead SUPPRESSED, and increments the sending
account's bounce_count_7d so health_monitor.py can throttle correctly.
"""

import re
from datetime import datetime, timezone

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.email.sender import _get_credentials
from src.db.models import Lead, SenderAccount, EmailEvent
from src.core.suppression import add_suppression
from src.core.state_machine import LeadStatus, transition, InvalidTransitionError

BOUNCE_SUBJECT_PATTERNS = [
    r"delivery status notification \(failure\)",
    r"undelivered mail returned to sender",
    r"mail delivery failed",
    r"delivery incomplete",
    r"address not found",
    r"message not delivered",
    r"wasn't delivered",
    r"couldn't be delivered",
    r"has been blocked",
    r"recipient inbox full",
    r"inbox full",
    r"delivery subsystem",
]

# Extracts the original recipient's email from the bounce message body,
# which typically quotes it near phrases like "The response was:" or
# lists it directly.
EMAIL_IN_BODY_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _is_bounce_subject(subject: str) -> bool:
    subject_lower = subject.lower()
    return any(re.search(pattern, subject_lower) for pattern in BOUNCE_SUBJECT_PATTERNS)


def _extract_subject(headers: list[dict]) -> str:
    for header in headers:
        if header["name"] == "Subject":
            return header["value"]
    return ""


def _extract_from_header(headers: list[dict]) -> str:
    for header in headers:
        if header["name"].lower() == "from":
            return header["value"]
    return ""


def check_for_bounces(session: Session, sender_account: SenderAccount, max_results: int = 20) -> dict:
    """
    Scans unread inbox messages for bounce notifications, matches the
    bounced address to a Lead, suppresses that lead permanently, and
    updates the sending account's bounce count.
    """
    creds = _get_credentials(sender_account.email)
    service = build("gmail", "v1", credentials=creds)

    summary = {"checked": 0, "bounces_found": 0}

    results = service.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
    ).execute()
    messages = results.get("messages", [])

    for msg_ref in messages:
        summary["checked"] += 1
        message = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="full"
        ).execute()

        headers = message["payload"]["headers"]
        subject = _extract_subject(headers)
        from_header = _extract_from_header(headers).lower()

        # Checking the sender address (Gmail's own "Mail Delivery
        # Subsystem", always mailer-daemon@/postmaster@) is far more
        # reliable than matching subject wording, since every
        # receiving server phrases its bounce subject differently —
        # "Address not found", "Message not delivered", etc. never
        # matched the old, narrower subject-only patterns at all.
        is_bounce_sender = "mailer-daemon" in from_header or "postmaster" in from_header
        if not (is_bounce_sender or _is_bounce_subject(subject)):
            continue

        # Pull the raw snippet Gmail provides — usually contains the
        # bounced address without needing to decode the full body.
        snippet = message.get("snippet", "")
        emails_found = EMAIL_IN_BODY_PATTERN.findall(snippet)

        bounced_lead = None
        for candidate_email in emails_found:
            lead = session.query(Lead).filter(Lead.email == candidate_email).first()
            if lead:
                bounced_lead = lead
                break

        if not bounced_lead:
            continue

        add_suppression(session, bounced_lead.email, reason="bounce_hard", permanent=True)

        try:
            bounced_lead.status = transition(LeadStatus(bounced_lead.status), LeadStatus.SUPPRESSED).value
        except InvalidTransitionError:
            bounced_lead.status = LeadStatus.SUPPRESSED.value

        sender_account.bounce_count_7d += 1

        previous_event = session.query(EmailEvent).filter(EmailEvent.lead_id == bounced_lead.id).first()
        if not previous_event:
            continue  # no prior campaign context to attach this bounce record to

        event = EmailEvent(
            lead_id=bounced_lead.id,
            campaign_id=previous_event.campaign_id,
            sender_account_id=sender_account.id,
            event_type="BOUNCE",
            scheduled_for=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
            notes=f"bounce detected: {subject}",
        )
        session.add(event)

        service.users().messages().modify(
            userId="me", id=msg_ref["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        summary["bounces_found"] += 1

    session.commit()
    return summary


def check_all_accounts_for_bounces(session: Session) -> dict:
    """Runs bounce detection for every ACTIVE sender account."""
    accounts = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    total = {"checked": 0, "bounces_found": 0}
    for acc in accounts:
        try:
            result = check_for_bounces(session, acc)
            total["checked"] += result["checked"]
            total["bounces_found"] += result["bounces_found"]
        except Exception as e:
            print(f"Bounce check failed for {acc.email}: {e}")
    return total