"""
DIAGNOSTIC ONLY — read-only, makes NO changes to the database.

Lists every QUEUED lead ("ready but not yet sent") and shows exactly
why it isn't going out right now: a bad-looking/code-like email,
suppression, outside its send window, or genuinely fine (just waiting
on timing/capacity).

Run from the project root:
    python diagnose_queued_leads.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db.session import SessionLocal, init_db
from src.db.models import Lead, SenderAccount
from src.email.timezone_resolver import is_within_send_window
from src.email.health_monitor import compute_capacity
from src.core.suppression import is_suppressed

# Same pattern the pipeline itself uses to validate an email's syntax.
STRICT_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Tokens that show up in code/markup but never in a real email address.
SUSPICIOUS_TOKENS = ["<", ">", "{", "}", ";", "function(", "function (", "var ", "==", "()", "\n", "\t", " "]


def looks_like_code(value: str) -> bool:
    return any(tok in value for tok in SUSPICIOUS_TOKENS)


def main():
    init_db()
    session = SessionLocal()

    queued = (
        session.query(Lead)
        .filter(Lead.status == "QUEUED")
        .order_by(Lead.created_at.asc())
        .all()
    )
    print(f"Total QUEUED leads: {len(queued)}\n")

    if not queued:
        print("Nothing is currently QUEUED.")
        session.close()
        return

    active_accounts = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    print("Sender accounts:")
    if not active_accounts:
        print("  ** NO ACTIVE SENDER ACCOUNTS ** — this alone would explain nothing sending.")
    for acc in active_accounts:
        cap = compute_capacity(acc)
        print(f"  {acc.email}: {cap.available_capacity} remaining today")
    print()

    for lead in queued:
        raw_email = lead.email or ""
        flags = []

        if not raw_email:
            flags.append("NO EMAIL ON RECORD")
        elif not STRICT_EMAIL_RE.match(raw_email):
            flags.append("FAILS STRICT EMAIL FORMAT CHECK")
        if raw_email and looks_like_code(raw_email):
            flags.append("LOOKS LIKE CODE / NOT A REAL EMAIL")
        if raw_email and is_suppressed(session, raw_email):
            flags.append("SUPPRESSED")
        if lead.timezone and not is_within_send_window(lead.timezone):
            flags.append(f"outside send window right now (timezone={lead.timezone})")
        elif not lead.timezone:
            flags.append("no timezone set")

        verdict = " | ".join(flags) if flags else "looks fine — just waiting on timing/capacity"
        print(f"[id {lead.id}] '{lead.business_name}'  email={raw_email!r}")
        print(f"    -> {verdict}\n")

    session.close()


if __name__ == "__main__":
    main()