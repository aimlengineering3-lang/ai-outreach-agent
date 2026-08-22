"""
Orchestrator — the agent loop that ties every phase together into a
real pipeline: discover -> research -> queue -> send -> log.

Runs independently of the Streamlit dashboard (can be triggered by cron
or APScheduler). Coordinates deterministic modules; does not itself
decide compliance-critical outcomes — those remain in state_machine.py
and suppression.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
from contextlib import redirect_stdout

import json
from datetime import datetime, timezone
import httpx

from src.db.session import SessionLocal, init_db
from src.db.models import Lead, LeadResearch, Campaign, CampaignTemplate, EmailEvent, SenderAccount

from src.discovery.maps_scraper import scrape_maps_listings
from src.discovery.deduplicator import is_likely_duplicate

from src.research.website_analyzer import analyze_website_with_contact_fallback
from src.research.pixel_detector import detect_tech_static
from src.research.contact_extractor import extract_contact_name
from src.research.email_validator import validate_email

from src.personalization.observation_selector import select_observations
from src.personalization.template_engine import render_template

from src.core.state_machine import LeadStatus, transition, InvalidTransitionError
from src.core.suppression import is_suppressed

from src.email.scheduler import get_due_actions
from src.email.timezone_resolver import resolve_timezone, is_within_send_window
from src.email.health_monitor import compute_capacity
from src.email.sender import send_email


FALLBACK_GREETING_TEMPLATE = "Hi {business_name} team,"


# ---------------------------------------------------------------------
# STAGE 1: DISCOVERY
# ---------------------------------------------------------------------
def discover_and_save(session, niche: str, city: str, state: str, max_results: int = 10) -> int:
    """
    Scrapes Maps listings and inserts only genuinely new leads. Checks
    each new listing against BOTH leads already in the database AND
    other listings already processed earlier in this same scrape —
    Google Maps sometimes returns the same business twice in one query
    (e.g. duplicate pins), so within-batch checking is required too.
    """
    query = f"{niche} in {city}, {state}"
    listings = scrape_maps_listings(query, max_results=max_results, headless=True)

    existing_leads = session.query(Lead).filter(Lead.niche == niche).all()
    newly_added_this_run = []  # tracks leads added within THIS call, for in-batch dedup
    inserted = 0

    for listing in listings:
        is_dup_against_db = any(
            is_likely_duplicate(
                listing.business_name, listing.website, city,
                existing.business_name, existing.website, existing.city,
            ).is_duplicate
            for existing in existing_leads
        )
        is_dup_against_this_batch = any(
            is_likely_duplicate(
                listing.business_name, listing.website, city,
                added.business_name, added.website, added.city,
            ).is_duplicate
            for added in newly_added_this_run
        )

        if is_dup_against_db or is_dup_against_this_batch:
            continue

        lead = Lead(
            business_name=listing.business_name, niche=niche, city=city, state=state,
            website=listing.website, phone=listing.phone, source="maps", status=LeadStatus.NEW.value,
        )
        session.add(lead)
        newly_added_this_run.append(lead)
        inserted += 1

    session.commit()
    return inserted


# ---------------------------------------------------------------------
# STAGE 2: RESEARCH
# ---------------------------------------------------------------------
def research_lead(session, lead: Lead) -> bool:
    """
    Runs all deterministic research steps for one lead, saves a
    LeadResearch row, updates contact/email fields, and transitions
    the lead to RESEARCHED.
    """
    if not lead.website:
        return False

    facts = analyze_website_with_contact_fallback(lead.website)
    tech = detect_tech_static(lead.website)

    if not facts.fetch_succeeded:
        return False

    try:
        html = httpx.get(lead.website, timeout=10.0, follow_redirects=True).text
        contact_name = extract_contact_name(html)
    except Exception:
        contact_name = None

    if contact_name:
        lead.contact_name = contact_name

    if facts.emails:
        candidate_email = facts.emails[0]
        validation = validate_email(candidate_email)
        lead.email = candidate_email
        lead.email_status = validation.status

    existing_research = session.query(LeadResearch).filter(LeadResearch.lead_id == lead.id).first()
    if existing_research:
        existing_research.meta_pixel = tech.meta_pixel
        existing_research.google_analytics = (tech.google_analytics == "PRESENT")
        existing_research.gtm = (tech.gtm == "PRESENT")
        existing_research.social_links = json.dumps({"facebook": facts.facebook_url, "instagram": facts.instagram_url})
        existing_research.observations = json.dumps(select_observations(facts))
        existing_research.researched_at = datetime.now(timezone.utc)
    else:
        research = LeadResearch(
            lead_id=lead.id,
            meta_pixel=tech.meta_pixel,
            google_analytics=(tech.google_analytics == "PRESENT"),
            gtm=(tech.gtm == "PRESENT"),
            capi_signal="unknown",
            social_links=json.dumps({"facebook": facts.facebook_url, "instagram": facts.instagram_url}),
            observations=json.dumps(select_observations(facts)),
        )
        session.add(research)

    # Only transition status if the lead is still NEW — if it's already
    # RESEARCHED (e.g. we're re-researching it to try finding an email
    # that was missed before), skip the transition entirely rather than
    # attempting an invalid RESEARCHED->RESEARCHED move, which would
    # trigger a rollback and wipe out the email/contact update we just made.
    if lead.status == LeadStatus.NEW.value:
        try:
            lead.status = transition(LeadStatus(lead.status), LeadStatus.RESEARCHED).value
        except InvalidTransitionError:
            session.rollback()
            return False

    session.commit()
    return True


# ---------------------------------------------------------------------
# STAGE 3: QUEUE
# ---------------------------------------------------------------------
def queue_researched_leads(session, campaign: Campaign) -> int:
    """
    Moves RESEARCHED leads matching this campaign's niche into QUEUED,
    provided they have a valid, non-suppressed email.
    """
    candidates = (
        session.query(Lead)
        .filter(Lead.status == LeadStatus.RESEARCHED.value, Lead.niche == campaign.niche)
        .all()
    )
    queued = 0

    needs_manual_review = 0
    for lead in candidates:
        if not lead.email or lead.email_status != "valid":
            needs_manual_review += 1
            continue
        if is_suppressed(session, lead.email):
            continue
        if not lead.timezone:
            lead.timezone = resolve_timezone(lead.city or "", lead.state or "")

        try:
            lead.status = transition(LeadStatus(lead.status), LeadStatus.QUEUED).value
            queued += 1
        except InvalidTransitionError:
            continue

    session.commit()
    return {"queued": queued, "needs_manual_review": needs_manual_review}


# ---------------------------------------------------------------------
# STAGE 4: SEND CYCLE
# ---------------------------------------------------------------------
def _variant_for_action(action_type: str, meta_pixel_status: str) -> str:
    if action_type == "SENT":
        return {"PRESENT": "pixel_found", "MISSING": "pixel_missing"}.get(meta_pixel_status, "pixel_unknown")
    return "followup_1" if action_type == "FOLLOWUP1" else "followup_2"


def run_send_cycle(session, campaign: Campaign) -> dict:
    """
    Finds due leads (scheduler), prioritizes follow-ups over brand-new
    sends, sends from the correct sender account (follow-ups always
    reuse the account that sent the original email — keeps threads
    consistent per prospect), and respects each account's remaining
    daily capacity.
    """
    summary = {"sent": 0, "skipped_no_capacity": 0, "skipped_outside_window": 0,
               "skipped_no_template": 0, "skipped_suppressed": 0}

    active_accounts = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    if not active_accounts:
        summary["skipped_no_capacity"] = -1
        return summary

    # Track remaining capacity per account for THIS run only (in-memory),
    # since sender_account.sent_today only updates in the DB after we
    # commit — without this, we could overshoot within a single run.
    remaining_capacity = {}
    for acc in active_accounts:
        cap = compute_capacity(acc)
        remaining_capacity[acc.id] = cap.available_capacity

    if sum(remaining_capacity.values()) <= 0:
        summary["skipped_no_capacity"] = -1
        return summary

    due_actions = get_due_actions(session, campaign)

    # Priority: follow-ups go first, so an existing conversation is
    # never starved by a fresh batch of brand-new leads.
    priority = {"FOLLOWUP2": 0, "FOLLOWUP1": 1, "SENT": 2}
    due_actions.sort(key=lambda a: priority.get(a.action_type, 3))

    for action in due_actions:
        lead = session.query(Lead).filter(Lead.id == action.lead_id).first()
        if not lead or not lead.email:
            continue
        if is_suppressed(session, lead.email):
            summary["skipped_suppressed"] += 1
            continue
        if lead.timezone and not is_within_send_window(lead.timezone):
            summary["skipped_outside_window"] += 1
            continue

        # Decide which sender account to use.
        if action.action_type == "SENT":
            # Brand-new lead: pick any account that still has capacity.
            sender_account = next(
                (acc for acc in active_accounts if remaining_capacity[acc.id] > 0), None
            )
        else:
            # Follow-up: MUST come from the same account that sent the
            # previous email to this lead, so the conversation stays
            # consistent from the prospect's point of view.
            last_event = (
                session.query(EmailEvent)
                .filter(EmailEvent.lead_id == lead.id)
                .order_by(EmailEvent.sent_at.desc())
                .first()
            )
            if not last_event:
                continue
            sender_account = next(
                (acc for acc in active_accounts if acc.id == last_event.sender_account_id), None
            )
            # If that specific account is out of capacity for today,
            # skip this lead for now — it will be retried on the next
            # pipeline run, not lost or sent from a different account.
            if sender_account and remaining_capacity[sender_account.id] <= 0:
                sender_account = None

        if not sender_account:
            summary["skipped_no_capacity"] += 1
            continue

        meta_pixel_status = lead.research.meta_pixel if lead.research else "UNKNOWN"
        variant = _variant_for_action(action.action_type, meta_pixel_status)

        if action.action_type == "FOLLOWUP2" and not campaign.followup2_enabled:
            continue

        template = (
            session.query(CampaignTemplate)
            .filter(CampaignTemplate.campaign_id == campaign.id, CampaignTemplate.variant == variant)
            .order_by(CampaignTemplate.updated_at.desc())
            .first()
        )
        if not template:
            summary["skipped_no_template"] += 1
            continue

        observations = (
            json.loads(lead.research.observations) if lead.research and lead.research.observations else []
        )

        render_result = render_template(
            template.body,
            {
                "first_name": f"Hi {lead.contact_name}," if lead.contact_name else None,
                "business_name": lead.business_name,
                "city": lead.city,
                "state": lead.state,
                "niche": lead.niche,
                "meta_pixel_status": meta_pixel_status,
                "website_observation": observations[0] if observations else "",
            },
            fallback_greeting=FALLBACK_GREETING_TEMPLATE.format(business_name=lead.business_name),
        )
        
        email_body_with_footer = (
            render_result.rendered_body
            + "\n\n---\nIf you'd prefer not to hear from us again, just reply with \"unsubscribe\" and we'll stop reaching out."
        )

        send_result = send_email(
            to_address=lead.email,
            subject=f"Quick note about {lead.business_name}",
            body=email_body_with_footer,
            sender_address=sender_account.email,
        )

        event = EmailEvent(
            lead_id=lead.id, campaign_id=campaign.id, sender_account_id=sender_account.id,
            event_type=action.action_type, template_used_id=template.id,
            scheduled_for=datetime.now(timezone.utc), sent_at=datetime.now(timezone.utc),
            notes=json.dumps({"test_mode": send_result.get("test_mode"), "message_id": send_result.get("message_id")}),
        )
        session.add(event)

        if action.action_type == "SENT":
            new_status = LeadStatus.CONTACTED
        elif action.action_type == "FOLLOWUP1":
            new_status = LeadStatus.NO_REPLY
        else:
            new_status = LeadStatus.COMPLETED

        try:
            lead.status = transition(LeadStatus(lead.status), new_status).value
        except InvalidTransitionError:
            pass

        sender_account.sent_today += 1
        remaining_capacity[sender_account.id] -= 1
        summary["sent"] += 1

    session.commit()
    return summary


# ---------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------
def run_pipeline(niche: str, city: str, state: str, campaign_id: int = None):
    init_db()
    session = SessionLocal()

    print(f"Searching for {niche} businesses in {city}, {state}...")
    new_count = discover_and_save(session, niche, city, state, max_results=25)

    if new_count == 0:
        print(f"No new businesses found — {city} looks fully covered for {niche} right now.")
    elif new_count < 25:
        print(f"Found {new_count} new business(es) — that's likely all of them for {city}.")
    else:
        print(f"Found {new_count} new business(es) — there may be more. Run this city again later to check.")

    print("")
    print("Researching newly found businesses...")
    new_leads = session.query(Lead).filter(Lead.status == LeadStatus.NEW.value, Lead.niche == niche).all()
    researched_count = sum(1 for lead in new_leads if research_lead(session, lead))
    if researched_count > 0:
        print(f"Completed research on {researched_count} business(es).")
    else:
        print("Nothing new to research right now.")

    if campaign_id:
        campaign = session.query(Campaign).filter(Campaign.id == campaign_id, Campaign.status == "ACTIVE").first()
    else:
        campaign = session.query(Campaign).filter(Campaign.niche == niche, Campaign.status == "ACTIVE").first()

    if not campaign:
        print("")
        print(f"No active campaign found for '{niche}'. Create and activate one from the Campaigns tab first.")
        session.close()
        return

    print("")
    print(f"Preparing eligible businesses for campaign '{campaign.name}'...")
    result = queue_researched_leads(session, campaign)
    if result["queued"] > 0:
        print(f"{result['queued']} business(es) are ready to be emailed.")
    if result["needs_manual_review"] > 0:
        print(
            f"{result['needs_manual_review']} business(es) had no email address found — "
            "check the Leads tab and contact them by phone instead."
        )

    print("")
    print("Sending emails...")
    summary = run_send_cycle(session, campaign)

    if summary["sent"] > 0:
        print(f"Sent {summary['sent']} email(s) successfully.")
    else:
        print("No emails were sent this time.")

    if summary.get("skipped_no_capacity") == -1:
        print("No active sender account with available capacity was found.")
    elif summary.get("skipped_no_capacity", 0) > 0:
        print(f"{summary['skipped_no_capacity']} email(s) skipped — the account that should send their follow-up is out of capacity today.")
    if summary["skipped_outside_window"] > 0:
        print(f"{summary['skipped_outside_window']} email(s) held back — it's outside business hours for those prospects right now.")
    if summary["skipped_no_template"] > 0:
        print(f"{summary['skipped_no_template']} email(s) skipped — no matching template found for that situation. Add one from the Campaigns tab.")
    if summary["skipped_suppressed"] > 0:
        print(f"{summary['skipped_suppressed']} email(s) skipped — those contacts are on the do-not-contact list.")

    total_in_city = session.query(Lead).filter(Lead.niche == niche, Lead.city == city).count()
    print("")
    print(f"Total {niche} leads found in {city} so far: {total_in_city}")

    session.close()

def run_pipeline_captured(niche: str, city: str, state: str, campaign_id: int = None) -> str:
    """
    Runs the pipeline and captures all print() output as a string, so
    the dashboard can display it instead of only the terminal.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        try:
            run_pipeline(niche, city, state, campaign_id)
        except Exception as e:
            print(f"ERROR: {e}")
    return buffer.getvalue()
if __name__ == "__main__":
    run_pipeline(niche="plumbing", city="Austin", state="TX")