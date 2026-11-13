"""
Detects bounce notification emails in the inbox (from Gmail's own
"Mail Delivery Subsystem"), matches them back to the lead whose email
bounced, marks that lead SUPPRESSED, and increments the sending
account's bounce_count_7d so health_monitor.py can throttle correctly.
"""

import re
import base64
from datetime import datetime, timezone

from googleapiclient.discovery import build
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.email.sender import _get_credentials
from src.email.outlook_client import is_outlook_address, fetch_recent_inbox, mark_read
from src.db.models import Lead, SenderAccount, EmailEvent
from src.core.suppression import suppress_everywhere, normalize_email
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
    r"^undeliverable",
]

# Gmail sends a "Delivery incomplete ... temporary problem ... will
# retry for N more hours" status update repeatedly (every several
# hours, for up to ~72h) WHILE a single delivery attempt is still
# being retried — this is NOT a bounce, just a progress notice. Left
# unchecked, one real problem address generates 4-6+ of these before
# Gmail either delivers it or truly gives up, and each one was being
# counted as a separate bounce — this is what was massively inflating
# bounce_count_7d relative to the real number of failed addresses.
RETRY_IN_PROGRESS_PATTERNS = [
    r"will retry",
    r"temporary problem",
    r"we('| wi)ll keep trying",
    r"delayed",
]


def _is_retry_in_progress(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in RETRY_IN_PROGRESS_PATTERNS)


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


BOUNCE_SENDER_MARKERS = ("mailer-daemon", "postmaster", "microsoftexchange")


def _is_bounce_message(subject: str, from_header: str) -> bool:
    from_lower = from_header.lower()
    is_bounce_sender = any(marker in from_lower for marker in BOUNCE_SENDER_MARKERS)
    return is_bounce_sender or _is_bounce_subject(subject)



def _walk_parts(payload):
    yield payload
    for part in payload.get("parts", []) or []:
        yield from _walk_parts(part)


def _gmail_full_text(message: dict) -> str:
    """Poori body (snippet sirf ~200 chars hota hai, address aksar uske baad aata hai)."""
    chunks = []
    for part in _walk_parts(message.get("payload", {})):
        data = (part.get("body") or {}).get("data")
        if not data:
            continue
        try:
            chunks.append(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "ignore"))
        except Exception:
            continue
    return " ".join(chunks)


def _failed_recipients(headers: list[dict], body_text: str) -> list[str]:
    """X-Failed-Recipients header / 'Final-Recipient:' line = bounce hone wala asli address."""
    found = []
    for h in headers:
        if h["name"].lower() == "x-failed-recipients":
            found += EMAIL_IN_BODY_PATTERN.findall(h["value"])
    for m in re.finditer(r"(?:final|original)-recipient:\s*(?:rfc822;)?\s*([^\s;]+)", body_text, re.I):
        found += EMAIL_IN_BODY_PATTERN.findall(m.group(1))
    return found


def _fetch_bounce_candidates(sender_account: SenderAccount, max_results: int):
    """
    Returns (messages, mark_read) for the account's provider. Each message is
    {"id", "subject", "from_header", "retry_text", "match_text"}:
      retry_text - what the "is this just a retry notice?" check looks at
      match_text - where the bounced recipient's address is searched for
    """
    if is_outlook_address(sender_account.email):
        messages = []
        for m in fetch_recent_inbox(sender_account.email, max(max_results, 100), days=30):
            body_text = m["body_text"]
            snippet = " ".join(body_text.split())[:300]
            messages.append({
                "id": m["id"],
                "subject": m["subject"],
                "from_header": m["from_header"],
                "retry_text": m["subject"] + " " + snippet,
                "match_text": body_text[:3000],
                "failed": _failed_recipients([], body_text),
                "received_ms": m.get("received_ms"),
                "unread": m.get("unread", True),
            })
        return messages, lambda message_id: mark_read(sender_account.email, message_id)

    creds = _get_credentials(sender_account.email)
    service = build("gmail", "v1", credentials=creds)
    results = service.users().messages().list(
        userId="me", labelIds=["INBOX"], maxResults=max(max_results, 200),
        q="from:(mailer-daemon OR postmaster) newer_than:30d -subject:Delay",
    ).execute()

    messages = []
    for msg_ref in results.get("messages", []):
        message = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="full"
        ).execute()
        headers = message["payload"]["headers"]
        subject = _extract_subject(headers)
        snippet = message.get("snippet", "")
        full_text = _gmail_full_text(message) or snippet
        messages.append({
            "id": msg_ref["id"],
            "subject": subject,
            "from_header": _extract_from_header(headers),
            "retry_text": subject + " " + snippet,
            "match_text": snippet + " " + full_text[:6000],
            "failed": _failed_recipients(headers, full_text),
            "received_ms": message.get("internalDate"),
            "unread": "UNREAD" in message.get("labelIds", []),
        })

    def mark_gmail_read(message_id: str) -> None:
        service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    return messages, mark_gmail_read


def _bounce_time(received_ms) -> datetime:
    """When the failure notice actually arrived, so a late scan can't make an old bounce look new."""
    try:
        return datetime.fromtimestamp(int(received_ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _record_bounce(
    session: Session, sender_account: SenderAccount, subject: str, text: str,
    received_ms, summary: dict, failed: list[str] | None = None,
) -> None:
    """
    Bounce ko GLOBALLY record karta hai.

    Pehle bug: agar is lead ka BOUNCE event pehle se ho to function suppression
    add kiye bina hi return ho jata tha, aur sirf pehla matching Lead row
    suppress hota tha. Ab:
      1. suppression + SUPPRESSED status HAR BAAR enforce hoti hai (idempotent),
         email ke har lead row par, kisi bhi campaign ka ho.
      2. sirf BOUNCE event / counter ek dafa badhta hai.
    """
    own_addresses = {normalize_email(sender_account.email)}
    candidates = [normalize_email(e) for e in (failed or [])]
    candidates += [normalize_email(e) for e in EMAIL_IN_BODY_PATTERN.findall(text)]
    candidates = [c for c in dict.fromkeys(candidates) if c and c not in own_addresses]

    bounced_lead = None
    for candidate_email in candidates:
        lead = session.query(Lead).filter(func.lower(func.trim(Lead.email)) == candidate_email).first()
        if lead:
            bounced_lead = lead
            break

    if not bounced_lead:
        # Lead nahi mila, lekin server ne khud bataya ki ye recipient fail hua -> phir bhi suppress.
        for addr in (normalize_email(e) for e in (failed or [])):
            if addr and addr not in own_addresses:
                suppress_everywhere(session, addr, reason="bounce_hard")
        print(f"[bounce_detector] unmatched bounce for {candidates} ({subject})")
        return

    # Global suppression: is email ke saare lead rows + permanent suppression row.
    suppress_everywhere(session, bounced_lead.email, reason="bounce_hard")

    already_counted = (
        session.query(EmailEvent)
        .filter(EmailEvent.lead_id == bounced_lead.id, EmailEvent.event_type == "BOUNCE")
        .first()
    )
    if already_counted:
        return  # event/counter dobara nahi badhana, suppression upar enforce ho chuki

    previous_event = (
        session.query(EmailEvent)
        .filter(EmailEvent.lead_id == bounced_lead.id)
        .order_by(EmailEvent.id.asc())
        .first()
    )
    if not previous_event:
        return

    when = _bounce_time(received_ms)
    session.add(EmailEvent(
        lead_id=bounced_lead.id,
        campaign_id=previous_event.campaign_id,
        sender_account_id=sender_account.id,
        event_type="BOUNCE",
        scheduled_for=when,
        sent_at=when,
        notes=f"bounce detected: {subject}",
    ))
    summary["bounces_found"] += 1


def check_for_bounces(session: Session, sender_account: SenderAccount, max_results: int = 20) -> dict:
    """
    Scans unread bounce notifications (Gmail or Outlook), matches the
    bounced address to a Lead, suppresses it permanently, and updates the
    sending account's bounce count. Retry/progress notices are marked
    read but never counted.
    """
    messages, mark_message_read = _fetch_bounce_candidates(sender_account, max_results)
    summary = {"checked": 0, "bounces_found": 0}

    for m in messages:
        summary["checked"] += 1
        if not _is_bounce_message(m["subject"], m["from_header"]):
            continue  # a normal email: leave it unread, untouched

        if m.get("unread", True):
            mark_message_read(m["id"])

        if _is_retry_in_progress(m["retry_text"]):
            continue

        _record_bounce(session, sender_account, m["subject"], m["match_text"], m.get("received_ms"), summary, m.get("failed"))

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