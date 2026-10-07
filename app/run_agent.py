"""
Orchestrator — the agent loop that ties every phase together into a
real pipeline: discover -> research -> queue -> send -> log.

Runs independently of the Streamlit dashboard (can be triggered by cron
or APScheduler). Coordinates deterministic modules; does not itself
decide compliance-critical outcomes — those remain in state_machine.py
and suppression.py.
"""

import sys
import time
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


# A business's name must contain at least one of these words to count
# as genuinely in-niche. Google Maps returns loosely-related categories
# for a niche search (hardware stores, unions, general contractors),
# so a plain keyword search is not enough on its own — see
# EXCLUDE_KEYWORDS below for names that get rejected regardless.
# Edit these lists freely as new false positives/negatives show up.
NICHE_KEYWORDS = {
    "plumbing": ["plumb", "pipe", "septic", "drain", "sewer", "pump", "mechanical", "heating", "hvac"],
    "hvac": ["hvac", "heating", "cooling", "air condition", "furnace", "mechanical", "refrigeration"],
    "roofing": ["roof", "gutter", "siding", "exterior"],
    "electrical": ["electric", "electrical", "wiring", "lighting"],
}

# Names containing any of these are rejected regardless of niche —
# these are categories that Maps includes as "related" but are never
# real outreach targets (supply stores, unions, clinics, etc.).
EXCLUDE_KEYWORDS = [
    "union", "training center", "hardware", "supply", "rental",
    "urology", "clinic", "hospital", "pharmacy", "wholesale",
    "distributor", "association",
]


def _is_in_niche(business_name: str, niche: str) -> bool:
    name_lower = business_name.lower()

    if any(bad in name_lower for bad in EXCLUDE_KEYWORDS):
        return False

    keywords = NICHE_KEYWORDS.get(niche)
    if not keywords:
        # Unknown niche — no keyword list configured, so don't filter.
        return True

    return any(kw in name_lower for kw in keywords)


# ---------------------------------------------------------------------
# STAGE 1: DISCOVERY
# ---------------------------------------------------------------------
def discover_and_save(session, niche: str, city: str, state: str, max_results: int = 10) -> tuple[int, bool]:
    """
    Scrapes Maps listings and inserts only genuinely new, in-niche
    leads. Checks each new listing against BOTH leads already in the
    database AND other listings already processed earlier in this same
    scrape — Google Maps sometimes returns the same business twice in
    one query (e.g. duplicate pins), so within-batch checking is
    required too. Returns (inserted_count, reached_max_results).
    """
    query = f"{niche} in {city}, {state}"
    existing_leads = session.query(Lead).filter(Lead.niche == niche).all()
    # Release the DB connection now — everything below (should_visit,
    # the whole Playwright scrape) works purely off the in-memory
    # existing_leads list and needs no further DB access until the
    # insert loop after scraping finishes. Without this, the query
    # above keeps the connection checked out for the entire scrape
    # (was ~150s) with the DB doing nothing during that time.
    session.commit()

    def should_visit(business_name: str) -> bool:
        # Cheap prefilter using only the name Maps already shows in its
        # list view, before that business's own page is ever opened.
        # This can only catch name-based duplicates (same city + a
        # similar name) since we don't have the candidate's website
        # yet — domain-based duplicates are still caught by the full
        # check below, after visiting, so no accuracy is lost. This
        # purely skips redundant page visits for businesses already
        # known, which matters most when re-running an already-covered
        # city.
        if not _is_in_niche(business_name, niche):
            return False
        already_known = any(
            is_likely_duplicate(
                business_name, None, city,
                existing.business_name, existing.website, existing.city,
            ).is_duplicate
            for existing in existing_leads
        )
        return not already_known

    scrape_result = scrape_maps_listings(
        query, max_results=max_results, headless=True, should_visit=should_visit,
    )
    listings = scrape_result.listings

    newly_added_this_run = []  # tracks leads added within THIS call, for in-batch dedup
    inserted = 0

    for listing in listings:
        if not _is_in_niche(listing.business_name, niche):
            continue

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
    return inserted, scrape_result.reached_max_results


# ---------------------------------------------------------------------
# STAGE 2: RESEARCH
# ---------------------------------------------------------------------
# After this many failed fetch attempts (across separate pipeline
# runs — each attempt already includes its own internal retry inside
# analyze_website_with_contact_fallback), a lead's website is treated
# as permanently unreachable and we stop re-paying the timeout cost on
# every future run. It still ends up correctly in the Manual Review
# tab (that's driven by lead.email being empty, not by status), it
# just stops being re-fetched.
MAX_RESEARCH_ATTEMPTS = 3


def research_lead(session, lead: Lead) -> bool:
    """
    Runs all deterministic research steps for one lead, saves a
    LeadResearch row, updates contact/email fields, and transitions
    the lead to RESEARCHED.
    """
    if not lead.website:
        # Nothing to ever fetch — this is a permanent, final outcome
        # (Facebook-page-only or no-website businesses), not a
        # transient failure, so finalize it now instead of leaving it
        # stuck in NEW to be checked again on every future run.
        if lead.status == LeadStatus.NEW.value:
            try:
                lead.status = transition(LeadStatus(lead.status), LeadStatus.RESEARCHED).value
            except InvalidTransitionError:
                session.rollback()
                return False
        session.commit()
        return True

    facts = analyze_website_with_contact_fallback(lead.website)
    tech = detect_tech_static(lead.website)

    if not facts.fetch_succeeded:
        lead.research_fetch_failures += 1

        if lead.research_fetch_failures >= MAX_RESEARCH_ATTEMPTS:
            # Given up enough transient-retry chances — treat as a
            # final "no email findable" outcome so this stops costing
            # a full timeout on every future pipeline run.
            if lead.status == LeadStatus.NEW.value:
                try:
                    lead.status = transition(LeadStatus(lead.status), LeadStatus.RESEARCHED).value
                except InvalidTransitionError:
                    session.rollback()
                    return False
            session.commit()
            return True

        # Still under the retry limit — leave it in NEW so a future
        # run (this city again, or the background worker's retry job)
        # gives it another chance, in case the failure was transient.
        session.commit()
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


def run_send_cycle(session, campaign: Campaign, max_sends: int | None = None) -> dict:
    """
    Finds due leads (scheduler), prioritizes follow-ups over brand-new
    sends, sends from the correct sender account (follow-ups always
    reuse the account that sent the original email — keeps threads
    consistent per prospect), and respects each account's remaining
    daily capacity.

    max_sends: optional cap on how many emails THIS call may send
    (used by the dashboard's per-niche send limits). None = no extra cap.
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
        cap = compute_capacity(session, acc)
        remaining_capacity[acc.id] = cap.available_capacity
    session.commit()  # persist any daily resets that just happened

    if sum(remaining_capacity.values()) <= 0:
        summary["skipped_no_capacity"] = -1
        return summary

    due_actions = get_due_actions(session, campaign)

    # Priority: follow-ups go first, so an existing conversation is
    # never starved by a fresh batch of brand-new leads.
    priority = {"FOLLOWUP2": 0, "FOLLOWUP1": 1, "SENT": 2}
    due_actions.sort(key=lambda a: priority.get(a.action_type, 3))

    for action in due_actions:
        if max_sends is not None and summary["sent"] >= max_sends:
            break
        lead = session.query(Lead).filter(Lead.id == action.lead_id).first()
        if not lead or not lead.email:
            continue
        if lead.niche != campaign.niche:
            # get_due_actions() only filters by status, not niche — without
            # this check, a Plumbing campaign send would also pick up
            # queued HVAC/Roofing/etc. leads.
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
            # consistent from the prospect's point of view. This is
            # also a fresh, last-second re-check of the lead's real
            # state (not the possibly-stale snapshot due_actions was
            # built from) - if some OTHER overlapping run (a second
            # manual click, or the background worker) already sent
            # this exact action in the meantime, last_event.event_type
            # will already reflect that, and we skip instead of
            # sending a duplicate.
            last_event = (
                session.query(EmailEvent)
                .filter(EmailEvent.lead_id == lead.id, EmailEvent.campaign_id == campaign.id)
                .order_by(EmailEvent.sent_at.desc())
                .first()
            )
            if not last_event:
                continue
            expected_prior_type = {"FOLLOWUP1": "SENT", "FOLLOWUP2": "FOLLOWUP1"}.get(action.action_type)
            if last_event.event_type != expected_prior_type:
                # Someone already advanced this lead past this stage
                # since the due list was built - stale, not a bug to
                # act on now.
                continue
            sender_account = next(
                (acc for acc in active_accounts if acc.id == last_event.sender_account_id), None
            )
            # If that specific account is out of capacity for today,
            # skip this lead for now - it will be retried on the next
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

        is_first_email = action.action_type == "SENT"
        subject = (
            f"Quick note about {lead.business_name}"
            if is_first_email
            else f"Re: {lead.email_subject or f'Quick note about {lead.business_name}'}"
        )

        try:
            send_result = send_email(
                to_address=lead.email,
                subject=subject,
                body=email_body_with_footer,
                sender_address=sender_account.email,
                in_reply_to_message_id=None if is_first_email else lead.email_message_id,
                thread_id=None if is_first_email else lead.email_thread_id,
            )
        except Exception as e:
            print(f"[send-error] Failed to send to {lead.business_name} ({lead.email}): {e}")
            continue

        if is_first_email:
            # Save these so every future follow-up to this lead can
            # thread onto this exact email instead of starting fresh.
            lead.email_subject = subject
            lead.email_message_id = send_result.get("message_id")
            lead.email_thread_id = send_result.get("gmail_thread_id")

        event = EmailEvent(
            lead_id=lead.id, campaign_id=campaign.id, sender_account_id=sender_account.id,
            event_type=action.action_type, template_used_id=template.id,
            scheduled_for=datetime.now(timezone.utc), sent_at=datetime.now(timezone.utc),
            notes=json.dumps({
                "test_mode": send_result.get("test_mode"),
                "message_id": send_result.get("message_id"),
                "gmail_id": send_result.get("gmail_id"),
            }),
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
def get_niche_stats(session) -> dict:
    """Har niche ke liye: naye leads pending, follow-up pending, aaj bheji gayi."""
    from datetime import datetime as _dt
    from sqlalchemy import func

    stats = {}

    def _bucket(niche):
        return stats.setdefault(niche, {"new_pending": 0, "followup_pending": 0, "sent_today": 0})

    niche_of_lead = dict(session.query(Lead.id, Lead.niche).all())

    campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()
    for c in campaigns:
        _bucket(c.niche)
        for action in get_due_actions(session, c):
            if niche_of_lead.get(action.lead_id) != c.niche:
                continue
            if action.action_type == "SENT":
                _bucket(c.niche)["new_pending"] += 1
            else:
                _bucket(c.niche)["followup_pending"] += 1

    start_of_day = _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        session.query(Lead.niche, func.count(EmailEvent.id))
        .join(EmailEvent, EmailEvent.lead_id == Lead.id)
        .filter(EmailEvent.sent_at >= start_of_day)
        .group_by(Lead.niche)
        .all()
    )
    for niche, count in rows:
        _bucket(niche)["sent_today"] = count

    return stats


def get_niche_stats(session) -> dict:
    """For each niche: new leads pending, follow-ups pending, sent today."""
    from datetime import datetime as _dt
    from sqlalchemy import func

    stats = {}

    def _bucket(niche):
        return stats.setdefault(niche, {"new_pending": 0, "followup_pending": 0, "sent_today": 0})

    niche_of_lead = dict(session.query(Lead.id, Lead.niche).all())

    campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()
    for c in campaigns:
        _bucket(c.niche)
        for action in get_due_actions(session, c):
            if niche_of_lead.get(action.lead_id) != c.niche:
                continue
            if action.action_type == "SENT":
                _bucket(c.niche)["new_pending"] += 1
            else:
                _bucket(c.niche)["followup_pending"] += 1

    start_of_day = _dt.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        session.query(Lead.niche, func.count(EmailEvent.id))
        .join(EmailEvent, EmailEvent.lead_id == Lead.id)
        .filter(EmailEvent.sent_at >= start_of_day)
        .group_by(Lead.niche)
        .all()
    )
    for niche, count in rows:
        _bucket(niche)["sent_today"] = count

    return stats


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def run_pipeline(niche: str, city: str, state: str, campaign_id: int = None):
    init_db()
    session = SessionLocal()
    started_at = time.time()

    new_count, reached_limit = discover_and_save(session, niche, city, state, max_results=150)

    new_leads = session.query(Lead).filter(
        Lead.status == LeadStatus.NEW.value, Lead.niche == niche, Lead.city == city,
    ).all()
    researched_count = sum(1 for lead in new_leads if research_lead(session, lead))
    emails_found = sum(1 for lead in new_leads if lead.email)
    no_email_found = len(new_leads) - emails_found

    if campaign_id:
        campaign = session.query(Campaign).filter(Campaign.id == campaign_id, Campaign.status == "ACTIVE").first()
    else:
        campaign = session.query(Campaign).filter(Campaign.niche == niche, Campaign.status == "ACTIVE").first()

    queued_count = 0
    if campaign:
        queued_count = queue_researched_leads(session, campaign)

    total_in_city = session.query(Lead).filter(Lead.niche == niche, Lead.city == city).count()
    elapsed = _format_duration(time.time() - started_at)

    print()
    print(f"{city}, {state} — {niche} pipeline finished in {elapsed}")
    more_note = "  (more may be available — run again to keep finding them)" if reached_limit else ""
    print(f"  New businesses found      : {new_count}{more_note}")
    print(f"  Businesses researched     : {researched_count}")
    print(f"  Emails found              : {emails_found}")
    print(f"  No email found            : {no_email_found}  (see Manual Review tab)")
    if campaign:
        print(f"  Queued for sending        : {queued_count}  (go to 'Send All Pending Now' to actually send)")
    else:
        print(f"  Queued for sending        : 0  (no active campaign for '{niche}' — create one in the Campaigns tab)")
    print(f"  Total {niche} leads in {city} so far: {total_in_city}")

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
            print(f"Something went wrong while running the pipeline: {e}")
    return buffer.getvalue()
if __name__ == "__main__":
    run_pipeline(niche="plumbing", city="Austin", state="TX")