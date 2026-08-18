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
    Scrapes Maps listings and inserts only genuinely new leads
    (checked via deduplicator against everything already saved for
    this niche). Returns count of new leads inserted.
    """
    query = f"{niche} in {city}, {state}"
    listings = scrape_maps_listings(query, max_results=max_results, headless=True)

    existing_leads = session.query(Lead).filter(Lead.niche == niche).all()
    inserted = 0

    for listing in listings:
        is_dup = any(
            is_likely_duplicate(
                listing.business_name, listing.website, city,
                existing.business_name, existing.website, existing.city,
            ).is_duplicate
            for existing in existing_leads
        )
        if is_dup:
            continue

        lead = Lead(
            business_name=listing.business_name, niche=niche, city=city, state=state,
            website=listing.website, source="maps", status=LeadStatus.NEW.value,
        )
        session.add(lead)
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
        # Re-research: update in place rather than inserting a duplicate
        # row, since a Lead has exactly one current research record.
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
    Finds due leads (scheduler), checks capacity/timezone/suppression,
    renders their template, sends, and logs the EmailEvent.
    """
    summary = {"sent": 0, "skipped_no_capacity": 0, "skipped_outside_window": 0,
               "skipped_no_template": 0, "skipped_suppressed": 0}

    sender_account = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").first()
    if not sender_account:
        summary["skipped_no_capacity"] = -1
        return summary

    capacity = compute_capacity(sender_account)
    if capacity.available_capacity <= 0:
        summary["skipped_no_capacity"] = -1
        return summary

    for action in get_due_actions(session, campaign):
        if summary["sent"] >= capacity.available_capacity:
            break

        lead = session.query(Lead).filter(Lead.id == action.lead_id).first()
        if not lead or not lead.email:
            continue
        if is_suppressed(session, lead.email):
            summary["skipped_suppressed"] += 1
            continue
        if lead.timezone and not is_within_send_window(lead.timezone):
            summary["skipped_outside_window"] += 1
            continue

        meta_pixel_status = lead.research.meta_pixel if lead.research else "UNKNOWN"
        variant = _variant_for_action(action.action_type, meta_pixel_status)

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

        send_result = send_email(
            to_address=lead.email,
            subject=f"Quick note about {lead.business_name}",
            body=render_result.rendered_body,
            sender_address=sender_account.email,
        )

        event = EmailEvent(
            lead_id=lead.id, campaign_id=campaign.id, sender_account_id=sender_account.id,
            event_type=action.action_type, template_used_id=template.id,
            scheduled_for=datetime.now(timezone.utc), sent_at=datetime.utcnow(),
            notes=json.dumps({"test_mode": send_result.get("test_mode"), "message_id": send_result.get("message_id")}),
        )
        session.add(event)

        if action.action_type == "SENT":
            new_status = LeadStatus.CONTACTED
        elif action.action_type == "FOLLOWUP1":
            new_status = LeadStatus.NO_REPLY
        else:  # FOLLOWUP2
            new_status = LeadStatus.COMPLETED

        try:
            lead.status = transition(LeadStatus(lead.status), new_status).value
        except InvalidTransitionError:
            pass

        sender_account.sent_today += 1
        summary["sent"] += 1

    session.commit()
    return summary


# ---------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------
def run_pipeline(niche: str, city: str, state: str):
    init_db()
    session = SessionLocal()

    print(f"[1/4] Discovering {niche} leads in {city}, {state}...")
    new_count = discover_and_save(session, niche, city, state, max_results=5)
    print(f"  -> {new_count} new leads saved.")

    print("[2/4] Researching NEW leads...")
    new_leads = session.query(Lead).filter(Lead.status == LeadStatus.NEW.value, Lead.niche == niche).all()
    researched_count = sum(1 for lead in new_leads if research_lead(session, lead))
    print(f"  -> {researched_count} leads researched.")

    campaign = session.query(Campaign).filter(Campaign.niche == niche, Campaign.status == "ACTIVE").first()
    if not campaign:
        print(f"[3/4] No ACTIVE campaign for niche '{niche}'. Create + activate one from the dashboard first.")
        session.close()
        return

    print(f"[3/4] Queueing researched leads into '{campaign.name}'...")
    result = queue_researched_leads(session, campaign)
    print(f"  -> {result['queued']} leads queued, {result['needs_manual_review']} need manual review (no valid email found — check phone/website).")

    print("[4/4] Running send cycle...")
    summary = run_send_cycle(session, campaign)
    print(f"  -> {summary}")

    session.close()


if __name__ == "__main__":
    run_pipeline(niche="plumbing", city="Austin", state="TX")