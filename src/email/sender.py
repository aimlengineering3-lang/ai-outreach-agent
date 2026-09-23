"""
Sends emails via the Gmail API. TEST_MODE gate is enforced here — when
True, every email is redirected to the sender's own inbox regardless of
the intended recipient, so no real prospect can accidentally be emailed
during development.
"""

import os
import base64
from email.mime.text import MIMEText
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDENTIALS_PATH = "secrets/credentials.json"
TOKEN_PATH = "secrets/token.json"

# TEST_MODE reads from .env so switching to production requires an
# explicit, deliberate change — never a code default.
def is_test_mode() -> bool:
    """Reads APP_MODE fresh from .env every call, so dashboard toggles apply immediately."""
    load_dotenv(override=True)
    return os.getenv("APP_MODE", "TEST") == "TEST"

def _get_credentials(sender_email: str = None) -> Credentials:
    """
    Loads cached OAuth token for the given sender account. Each Gmail
    account needs its own token file since each was authorized separately.
    If a cached token's refresh fails (e.g. revoked/invalid_grant), this
    falls back to a fresh interactive authorization instead of crashing.
    """
    token_path = f"secrets/token_{sender_email}.json" if sender_email else TOKEN_PATH

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    needs_new_auth = not creds or not creds.valid

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            needs_new_auth = False
        except Exception:
            # Refresh token itself is dead (revoked/invalid_grant) —
            # nothing to do but re-authorize interactively.
            needs_new_auth = True

    if needs_new_auth:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(token_path, "w") as token_file:
        token_file.write(creds.to_json())

    return creds


def send_email(
    to_address: str,
    subject: str,
    body: str,
    sender_address: str,
    self_test_address: Optional[str] = None,
) -> dict:
    """
    Sends an email via Gmail API. If TEST_MODE is True, the actual
    recipient is overridden with self_test_address (defaults to
    sender_address itself) regardless of what `to_address` was — this
    makes it structurally impossible to accidentally email a real
    prospect while developing.
    """
    creds = _get_credentials(sender_address)
    service = build("gmail", "v1", credentials=creds)

    actual_recipient = to_address
    if is_test_mode():
        actual_recipient = self_test_address or sender_address
        subject = f"[TEST MODE - would send to {to_address}] {subject}"

    message = MIMEText(body)
    message["to"] = actual_recipient
    message["from"] = sender_address
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return {
        "message_id": result.get("id"),
        "actual_recipient": actual_recipient,
        "test_mode": is_test_mode(),
    }


if __name__ == "__main__":
    result = send_email(
        to_address="a-real-prospect-would-go-here@example.com",
        subject="Quick question about your website",
        body="Hi there, this is a test email from the outreach agent (TEST MODE).",
        sender_address="marketingwithusman9@gmail.com",
    )
    print(result)