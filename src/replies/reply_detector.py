"""
Checks the sender's Gmail inbox for new replies to outreach emails,
matches them to the correct Lead by sender email address, and triggers
the appropriate state transition (REPLIED -> STOPPED for automated
follow-ups) plus classification.

This is the piece that turns reply_classifier.py from a standalone
function into something the pipeline actually uses.
"""

import base64
from datetime import datetime

from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from src.email.sender import _get_credentials
from src.db.models import Lead, EmailEvent, Campaign
from src.core.state_machine import LeadStatus, transition, InvalidTransitionError
from src.replies.reply_classifier import classify_reply


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


def check_for_replies(session: Session, campaign: Campaign, max_results: int = 20) -> dict:
    """
    Fetches recent unread messages from the sender's inbox, matches each
    to a Lead by sender email, classifies the reply, logs a REPLY
    EmailEvent, and transitions the lead to STOPPED (per the requirement
    that ANY reply immediately halts automated follow-ups).
    """
    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds)

    summary = {"checked": 0, "matched_replies": 0, "unmatched": 0}

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

        event = EmailEvent(
            lead_id=lead.id,
            campaign_id=campaign.id,
            sender_account_id=1,  # TODO: resolve properly once multi-account routing exists
            event_type="REPLY",
            scheduled_for=datetime.utcnow(),
            sent_at=datetime.utcnow(),
            notes=f"category={category}",
        )
        session.add(event)

        # Per requirement: ANY reply stops automated follow-ups immediately,
        # regardless of category. Category is stored for the human to see,
        # not used to decide whether to stop.
        try:
            lead.status = transition(LeadStatus(lead.status), LeadStatus.REPLIED).value
            lead.status = transition(LeadStatus(lead.status), LeadStatus.STOPPED).value
        except InvalidTransitionError:
            pass

        # Mark as read so we don't reprocess it next run
        service.users().messages().modify(
            userId="me", id=msg_ref["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()

        summary["matched_replies"] += 1

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