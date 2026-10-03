"""
Checks the sender's Gmail inbox for new replies to outreach emails,
matches them to the correct Lead by sender email address, and triggers
the appropriate state transition (REPLIED -> STOPPED for automated
follow-ups) plus classification.

This is the piece that turns reply_classifier.py from a standalone
function into something the pipeline actually uses.
"""
import io
import time
from contextlib import redirect_stdout
import base64
from datetime import datetime, timezone
from googleapiclient.discovery import build
from sqlalchemy.orm import Session
from src.email.sender import send_email
from src.core.config import load_settings
from datetime import datetime as dt
from src.email.sender import _get_credentials
from src.db.models import Lead, EmailEvent, Campaign, SenderAccount
from src.core.state_machine import LeadStatus, transition, InvalidTransitionError
import re
from src.replies.reply_classifier import classify_reply
from src.replies.night_responder import generate_night_response
from src.email.sender import send_email
from src.email.timezone_resolver import is_within_send_window

# A simple, dependency-free safety net: even if the LLM classifier
# fails or mis-reads a short reply, an explicit unsubscribe-style
# phrase must never be missed — this is compliance-relevant, not just
# a nice-to-have, so it doesn't rely on the LLM call succeeding.
UNSUBSCRIBE_FALLBACK_PATTERN = re.compile(
    r"\b(unsubscribe|remove me|take me off|stop emailing|stop contacting|do not contact)\b",
    re.IGNORECASE,
)

def _extract_sender_email(headers: list[dict]) -> str | None:
    for header in headers:
        if header["name"] == "From":
            # "From" header looks like: "John Smith <john@abcplumbing.com>"
            raw = header["value"]
            if "<" in raw and ">" in raw:
                return raw.split("<")[1].split(">")[0].strip().lower()
            return raw.strip().lower()
    return None


def _extract_body_text(payload: dict) -> str:
    """
    Gmail API returns message body as base64-encoded parts, possibly
    nested (multipart). This walks the structure to find plain text.
    """
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        # Fallback: recurse into nested multipart
        for part in payload["parts"]:
            text = _extract_body_text(part)
            if text:
                return text
        return ""

    data = payload.get("body", {}).get("data", "")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def check_for_replies(session: Session, campaign: Campaign, sender_account_email: str = None, max_results: int = 20) -> dict:
    """
    Fetches recent unread messages from the sender's inbox, matches each
    to a Lead by sender email, classifies the reply, logs a REPLY
    EmailEvent, and transitions the lead to STOPPED (per the requirement
    that ANY reply immediately halts automated follow-ups).
    """
    creds = _get_credentials(sender_account_email)
    service = build("gmail", "v1", credentials=creds)

    summary = {"checked": 0, "matched_replies": 0, "unmatched": 0, "matches": []}

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
        sender_email = _extract_sender_email(headers)
        if not sender_email:
            continue

        lead = session.query(Lead).filter(Lead.email == sender_email).first()
        if not lead:
            summary["unmatched"] += 1
            continue

        body_text = _extract_body_text(message["payload"])
        category = classify_reply(body_text)

        if category != "unsubscribe" and UNSUBSCRIBE_FALLBACK_PATTERN.search(body_text):
            category = "unsubscribe"

        if category == "unsubscribe":
            from src.core.suppression import add_suppression
            add_suppression(session, lead.email, reason="unsubscribe", permanent=True)

        matched_account = (
            session.query(SenderAccount).filter(SenderAccount.email == sender_account_email).first()
            if sender_account_email else None
        )

        event = EmailEvent(
            lead_id=lead.id,
            campaign_id=campaign.id,
            sender_account_id=matched_account.id if matched_account else None,
            event_type="REPLY",
            scheduled_for=datetime.now(timezone.utc),
            sent_at=datetime.now(timezone.utc),
            notes=f"category={category}",
        )
        session.add(event)

        # This was the missing piece: logging the REPLY event alone
        # never stopped future follow-ups — only this status change
        # does, since the scheduler only queries leads still in
        # QUEUED/CONTACTED/NO_REPLY. Without it, a lead kept getting
        # automated follow-ups even after replying.
        try:
            lead.status = transition(LeadStatus(lead.status), LeadStatus.REPLIED).value
        except InvalidTransitionError:
            pass

                # If it's currently your quiet hours (e.g. late at night, when
        # you're asleep), send a brief acknowledgement so the prospect
        # isn't left waiting with no response until morning.
        import pytz
        settings = load_settings()
        quiet_hours = settings.get(
            "your_quiet_hours",
            {"start_hour": 23, "end_hour": 8, "timezone": "Asia/Karachi"}
        )
        your_tz = pytz.timezone(quiet_hours["timezone"])
        your_current_hour = dt.now(your_tz).hour

        start = quiet_hours["start_hour"]
        end = quiet_hours["end_hour"]
        # Quiet hours wrap past midnight (e.g. 23 -> 8), so this check
        # differs from a normal same-day range.
        if start > end:
            is_quiet_hours = your_current_hour >= start or your_current_hour < end
        else:
            is_quiet_hours = start <= your_current_hour < end

        if is_quiet_hours:
            night_response = generate_night_response(
                first_name=lead.contact_name, sender_name="Usman"
            )
            try:
                send_email(
                    to_address=lead.email,
                    subject=f"Re: {lead.email_subject or f'Quick note about {lead.business_name}'}",
                    body=night_response.body,
                    # Use the account whose inbox this reply actually
                    # came in on — not a hardcoded account — so the
                    # acknowledgement comes from the same conversation
                    # the prospect is already in.
                    sender_address=sender_account_email,
                    in_reply_to_message_id=lead.email_message_id,
                    thread_id=lead.email_thread_id,
                )
            except Exception:
                pass  # Don't let a failed acknowledgement break reply detection

        # Mark as read so we don't reprocess it next run
        service.users().messages().modify(
            userId="me", id=msg_ref["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        summary["matched_replies"] += 1
        summary["matches"].append({"business_name": lead.business_name, "category": category})

    session.commit()
    return summary


if __name__ == "__main__":
    from src.db.session import SessionLocal, init_db
    from src.db.models import Campaign

    init_db()
    session = SessionLocal()

    campaign = session.query(Campaign).filter(Campaign.status == "ACTIVE").first()
    if campaign:
        result = check_for_replies(session, campaign)
        print(result)
    else:
        print("No active campaign found.")

    session.close()

def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def check_all_active_campaigns_captured() -> str:
    """
    Runs reply-check for every ACTIVE campaign, across ALL sender
    accounts - since a reply could arrive in any account's inbox
    depending on which account sent the original email.
    """
    from src.db.session import SessionLocal, init_db
    from src.db.models import Campaign, SenderAccount

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        started_at = time.time()
        init_db()
        session = SessionLocal()
        campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()
        accounts = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()

        if not campaigns or not accounts:
            if not campaigns:
                print("No active campaigns to check.")
            if not accounts:
                print("No active sender accounts to check.")
            session.close()
            return buffer.getvalue()

        total_checked = 0
        total_unmatched = 0
        all_matches = []
        errors = []

        for campaign in campaigns:
            for account in accounts:
                try:
                    result = check_for_replies(session, campaign, sender_account_email=account.email)
                    total_checked += result["checked"]
                    total_unmatched += result["unmatched"]
                    all_matches.extend(result["matches"])
                except Exception as e:
                    errors.append(f"{campaign.name} ({account.email}): {e}")

        session.close()
        elapsed = _format_duration(time.time() - started_at)

        category_counts = {}
        for m in all_matches:
            category_counts[m["category"]] = category_counts.get(m["category"], 0) + 1
        category_str = ", ".join(f"{cat}: {count}" for cat, count in category_counts.items())

        print(f"Reply check finished in {elapsed}")
        print(f"  Accounts checked         : {len(accounts)}")
        print(f"  Unread messages checked  : {total_checked}")
        print(f"  New replies matched      : {len(all_matches)}" + (f"  ({category_str})" if category_str else ""))
        print(f"  Unrelated/unmatched mail : {total_unmatched}")
        if all_matches:
            print()
            print("  Replies (follow-ups stopped for these):")
            for m in all_matches:
                print(f"    - {m['business_name']} : {m['category']}")
        if errors:
            print()
            print("  Errors:")
            for err in errors:
                print(f"    - {err}")

    return buffer.getvalue()