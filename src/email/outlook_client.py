"""
Outlook (personal Microsoft account) support via MSAL + Microsoft Graph.

Each account gets its own token cache file in secrets/, same idea as the
per-account Gmail token files. First run opens a browser for login and
consent; after that tokens refresh silently.
"""

import base64
import os
from pathlib import Path

import httpx
import msal
from dotenv import load_dotenv

load_dotenv()

# MSAL adds offline_access (refresh tokens) automatically. Passing it
# explicitly raises an error, so it must NOT be listed here.
SCOPES = ["Mail.Send", "Mail.ReadWrite", "User.Read"]
GRAPH_URL = "https://graph.microsoft.com/v1.0"


class OutlookQuotaExceededError(RuntimeError):
    """Microsoft Graph said this account's daily send quota is used up."""
OUTLOOK_DOMAINS = ("outlook.com", "hotmail.com", "live.com", "msn.com")


def is_outlook_address(email: str) -> bool:
    return email.lower().split("@")[-1] in OUTLOOK_DOMAINS


def _cache_path(email: str) -> Path:
    return Path("secrets") / f"msal_cache_{email.lower()}.json"


def _load_cache(email: str) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    path = _cache_path(email)
    if path.exists():
        cache.deserialize(path.read_text(encoding="utf-8"))
    return cache


def _save_cache(email: str, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        path = _cache_path(email)
        path.parent.mkdir(exist_ok=True)
        path.write_text(cache.serialize(), encoding="utf-8")


def get_access_token(email: str, interactive: bool = False) -> str:
    load_dotenv(override=True)
    client_id = os.getenv("OUTLOOK_CLIENT_ID")
    authority = os.getenv("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/consumers")
    if not client_id:
        raise RuntimeError("OUTLOOK_CLIENT_ID is missing in .env")

    cache = _load_cache(email)
    app = msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)

    result = None
    for account in app.get_accounts(username=email):
        result = app.acquire_token_silent(SCOPES, account=account)
        if result and "access_token" in result:
            break
        result = None

    if not result:
        if not interactive:
            raise RuntimeError(
                f"Outlook login for {email} is missing or expired. "
                f'Run: python scripts/authorize_outlook.py "{email}"'
            )
        result = app.acquire_token_interactive(SCOPES, login_hint=email)
        if "access_token" not in result:
            raise RuntimeError(
                f"Outlook login failed: {result.get('error')} - {result.get('error_description')}"
            )

        # Same safety idea as the Gmail flow: make sure the browser
        # signed in as the account we asked for, before saving anything.
        claims = result.get("id_token_claims", {})
        authorized = (claims.get("preferred_username") or claims.get("email") or "").lower()
        if authorized and authorized != email.lower():
            raise RuntimeError(
                f"Authorized the wrong Microsoft account: expected '{email}' "
                f"but signed in as '{authorized}'. Nothing was saved or sent."
            )

    _save_cache(email, cache)
    return result["access_token"]


def send_mime_via_graph(sender_email: str, mime_bytes: bytes) -> None:
    """Sends a fully built MIME message (headers included) via Graph."""
    token = get_access_token(sender_email)
    response = httpx.post(
        f"{GRAPH_URL}/me/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
        content=base64.b64encode(mime_bytes),
        timeout=30,
    )
    if response.status_code != 202:
        if response.status_code == 429 or "ErrorExceededMessageLimit" in response.text:
            raise OutlookQuotaExceededError(
                f"Graph sendMail failed ({response.status_code}): {response.text}"
            )
        raise RuntimeError(f"Graph sendMail failed ({response.status_code}): {response.text}")



def _graph_get(email: str, path: str, params: dict | None = None, extra_headers: dict | None = None) -> dict:
    token = get_access_token(email)
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    response = httpx.get(f"{GRAPH_URL}{path}", params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_unread_inbox(email: str, max_results: int = 20) -> list[dict]:
    """
    Returns unread inbox messages in a provider-neutral shape, so reply and
    bounce detection don't need to know Graph's response format.
    """
    data = _graph_get(
        email,
        "/me/mailFolders/inbox/messages",
        params={
            "$filter": "isRead eq false",
            "$top": max_results,
            "$select": "id,subject,from,body,bodyPreview,receivedDateTime",
        },
        extra_headers={"Prefer": 'outlook.body-content-type="text"'},
    )

    messages = []
    for item in data.get("value", []):
        sender = (item.get("from") or {}).get("emailAddress", {})
        address = (sender.get("address") or "").lower()
        messages.append({
            "id": item["id"],
            "from_email": address,
            "from_header": f'{sender.get("name", "")} <{address}>',
            "subject": item.get("subject") or "",
            "body_text": (item.get("body") or {}).get("content", ""),
            "snippet": item.get("bodyPreview") or "",
        })
    return messages


def mark_read(email: str, message_id: str) -> None:
    token = get_access_token(email)
    response = httpx.patch(
        f"{GRAPH_URL}/me/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"isRead": True},
        timeout=30,
    )
    response.raise_for_status()


def fetch_recent_inbox(email: str, max_results: int = 100, days: int = 30) -> list[dict]:
    """
    Pichhle `days` din ka inbox (read + unread dono). Bounce detection ko
    read/unread se independent rakhne ke liye — user ne notice khol li to bhi miss na ho.
    """
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _graph_get(
        email,
        "/me/mailFolders/inbox/messages",
        params={
            "$filter": f"receivedDateTime ge {since}",
            "$top": max_results,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,body,bodyPreview,receivedDateTime,isRead",
        },
        extra_headers={"Prefer": 'outlook.body-content-type="text"'},
    )
    messages = []
    for item in data.get("value", []):
        sender = (item.get("from") or {}).get("emailAddress", {})
        address = (sender.get("address") or "").lower()
        received_ms = None
        try:
            dt = datetime.fromisoformat((item.get("receivedDateTime") or "").replace("Z", "+00:00"))
            received_ms = int(dt.timestamp() * 1000)
        except ValueError:
            pass
        messages.append({
            "id": item["id"],
            "from_email": address,
            "from_header": f'{sender.get("name", "")} <{address}>',
            "subject": item.get("subject") or "",
            "body_text": (item.get("body") or {}).get("content", ""),
            "snippet": item.get("bodyPreview") or "",
            "received_ms": received_ms,
            "unread": not item.get("isRead", False),
        })
    return messages
