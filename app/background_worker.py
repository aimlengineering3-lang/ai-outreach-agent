"""
Background worker — runs independently of the Streamlit dashboard.
Every 30 minutes, checks all active campaigns for leads whose sending
window (their own US timezone) has just opened, and sends their due
emails automatically. No manual "Run Pipeline" click needed for
timing — you only need to run discovery/research periodically (or
this worker can be extended to do that too).

Run this as a separate, always-on process:
    python -m app.background_worker
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from datetime import datetime
from src.replies.bounce_detector import check_all_accounts_for_bounces
from apscheduler.schedulers.blocking import BlockingScheduler
from src.core.config import load_settings
from app.run_agent import run_pipeline
from src.db.session import SessionLocal, init_db
from src.db.models import Campaign
from app.run_agent import run_send_cycle
from src.replies.reply_detector import check_for_replies


def send_due_emails_job():
    """
    Checks every ACTIVE campaign and sends any email that is due right
    now — this INCLUDES leads that were queued earlier but skipped
    because it wasn't their business hours yet. Since this runs every
    30 minutes, as soon as a prospect's local time enters the sending
    window, their email goes out on the next tick — no manual re-run
    required.
    """
    init_db()
    session = SessionLocal()
    campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()

    total_sent = 0
    for campaign in campaigns:
        try:
            summary = run_send_cycle(session, campaign)
            total_sent += summary["sent"]
        except Exception as e:
            print(f"[{datetime.now()}] Error sending for '{campaign.name}': {e}")

    print(f"[{datetime.now()}] Send check complete — {total_sent} email(s) sent this run.")
    session.close()

def discover_new_leads_job():
    """
    Cycles through target_cities (one city per run, rotating) across
    all niches, so new leads keep getting discovered without you
    needing to click "Run Pipeline Now" every day.
    """
    init_db()
    settings = load_settings()
    cities = settings.get("target_cities", [])
    if not cities:
        print(f"[{datetime.now()}] No target cities configured — skipping discovery.")
        return

    # Rotate through cities using the current hour as a simple index,
    # so different cities get tried across different runs.
    index = datetime.now().hour % len(cities)
    city_entry = cities[index]

    for niche in ["plumbing", "hvac", "roofing", "electrical"]:
        try:
            run_pipeline(niche, city_entry["city"], city_entry["state"])
        except Exception as e:
            print(f"[{datetime.now()}] Discovery error for {niche} in {city_entry['city']}: {e}")

    print(f"[{datetime.now()}] Discovery cycle complete for {city_entry['city']}, {city_entry['state']}.")

def check_replies_job():
    """
    Checks the inbox for new replies every 30 minutes and stops
    follow-ups automatically for anyone who replied — no manual
    "Check Replies" click needed either.
    """
    init_db()
    session = SessionLocal()
    campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()

    total_replies = 0
    for campaign in campaigns:
        try:
            result = check_for_replies(session, campaign)
            total_replies += result["matched_replies"]
        except Exception as e:
            print(f"[{datetime.now()}] Error checking replies for '{campaign.name}': {e}")

    print(f"[{datetime.now()}] Reply check complete — {total_replies} new repl(y/ies) found this run.")
    session.close()

def check_bounces_job():
    """
    Checks for bounce notification emails and suppresses/updates
    sender health accordingly, every 30 minutes.
    """
    init_db()
    session = SessionLocal()
    try:
        result = check_all_accounts_for_bounces(session)
        print(f"[{datetime.now()}] Bounce check complete — {result['bounces_found']} bounce(s) found this run.")
    except Exception as e:
        print(f"[{datetime.now()}] Error checking bounces: {e}")
    session.close()

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(discover_new_leads_job, "interval", hours=4, id="discover_new_leads")
    scheduler.add_job(check_bounces_job, "interval", minutes=30, id="check_bounces")

    # Every 30 minutes: send any email whose recipient's business hours
    # have just opened.
    scheduler.add_job(send_due_emails_job, "interval", minutes=30, id="send_due_emails")

    # Every 30 minutes: check for replies and stop follow-ups if needed.
    scheduler.add_job(check_replies_job, "interval", minutes=30, id="check_replies")

    print("Background worker started. Checking every 30 minutes for due emails and replies.")
    print("Leave this window open (or run it in the background) — press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Background worker stopped.")