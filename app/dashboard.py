"""
Streamlit control panel — read/write against the same SQLite database
the background engine uses. This file NEVER runs scraping/sending logic
itself; it only queries, displays, and writes control flags (e.g.
pausing a campaign) that the background engine/scheduler reads.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, date

import streamlit as st
from sqlalchemy import func

from src.db.session import SessionLocal, init_db
from src.db.models import (
    Lead, Campaign, CampaignTemplate, EmailEvent, SenderAccount, SuppressionList,
)
from src.email.health_monitor import compute_capacity

init_db()

st.set_page_config(
    page_title="AI Outreach Agent",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

:root {
    --ink: #1A2233;
    --slate: #5B6478;
    --accent: #E85D2F;
    --accent-soft: #FDEDE6;
    --border: #E6E8EE;
    --bg-panel: #FFFFFF;
}

.stApp { background-color: #F6F7FA; }

section[data-testid="stSidebar"] {
    background-color: #1A2233;
}
section[data-testid="stSidebar"] * { color: #E8EAF0 !important; }
section[data-testid="stSidebar"] .stRadio label:hover { color: var(--accent) !important; }

h1, h2, h3 { color: var(--ink) !important; font-weight: 700 !important; }

.hero {
    padding: 4px 0 18px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 22px;
}
.hero-title { font-size: 30px; font-weight: 800; color: var(--ink); margin: 0; }
.hero-sub { font-size: 14px; color: var(--slate); margin-top: 4px; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; letter-spacing: 0.02em;
}
.badge-active { background: #E4F5EA; color: #1E8A4C; }
.badge-paused { background: #F1F2F5; color: #5B6478; }
.badge-warn { background: #FDEDE6; color: #C24A1E; }

div[data-testid="stMetric"] {
    background: var(--bg-panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 18px;
}
div[data-testid="stMetricLabel"] { color: var(--slate) !important; font-weight: 500; }
div[data-testid="stMetricValue"] { color: var(--ink) !important; }

.stButton > button {
    border-radius: 8px; font-weight: 600; border: 1px solid var(--border);
}
.stButton > button[kind="primary"] {
    background-color: var(--accent); border-color: var(--accent);
}

.section-label {
    font-size: 12px; font-weight: 700; color: var(--slate);
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;
}

.empty-state {
    border: 1px dashed var(--border); border-radius: 12px;
    padding: 32px; text-align: center; color: var(--slate);
    background: var(--bg-panel);
}
</style>
""", unsafe_allow_html=True)

session = SessionLocal()

NICHES = ["plumbing", "hvac", "roofing", "electrical"]
TEMPLATE_VARIANTS = ["pixel_found", "pixel_missing", "pixel_unknown", "followup_1", "followup_2"]
AVAILABLE_VARIABLES = [
    "first_name", "business_name", "city", "state", "niche",
    "meta_pixel_status", "website_observation",
]


def status_badge(status: str) -> str:
    mapping = {
        "ACTIVE": "badge-active", "PAUSED": "badge-paused",
        "THROTTLED": "badge-warn",
    }
    css_class = mapping.get(status, "badge-paused")
    return f'<span class="badge {css_class}">{status}</span>'


def get_latest_template(campaign_id: int, variant: str):
    return (
        session.query(CampaignTemplate)
        .filter(CampaignTemplate.campaign_id == campaign_id, CampaignTemplate.variant == variant)
        .order_by(CampaignTemplate.updated_at.desc())
        .first()
    )


# ---------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📬 Outreach Agent")
    page = st.radio(
        "Navigate",
        ["Overview", "Campaigns", "Leads", "Sender Accounts", "Suppression List"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption(f"DB status: connected · {datetime.now().strftime('%b %d, %H:%M')}")

st.markdown(
    '<div class="hero">'
    '<p class="hero-title">AI Home Services Outreach Agent</p>'
    '<p class="hero-sub">Plumbing · HVAC · Roofing · Electrical — US market</p>'
    '</div>',
    unsafe_allow_html=True,
)

# =======================================================================
# OVERVIEW
# =======================================================================
if page == "Overview":
    total_leads = session.query(Lead).count()
    researched = session.query(Lead).filter(Lead.status != "NEW").count()

    today_start = datetime.combine(date.today(), datetime.min.time())
    sent_today = (
        session.query(EmailEvent)
        .filter(EmailEvent.event_type == "SENT", EmailEvent.sent_at >= today_start)
        .count()
    )
    replies = session.query(EmailEvent).filter(EmailEvent.event_type == "REPLY").count()
    bounces = session.query(EmailEvent).filter(EmailEvent.event_type == "BOUNCE").count()
    suppressed = session.query(SuppressionList).count()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Leads Discovered", total_leads)
    c2.metric("Researched", researched)
    c3.metric("Emails Sent Today", sent_today)
    c4.metric("Replies", replies)
    c5.metric("Suppressed", suppressed)

    st.write("")
    st.markdown('<div class="section-label">Leads by Status</div>', unsafe_allow_html=True)

    status_counts = dict(
        session.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    )
    with st.container(border=True):
        if status_counts:
            st.bar_chart(status_counts, color="#E85D2F")
        else:
            st.markdown(
                '<div class="empty-state">No leads yet. Head to the <b>Leads</b> tab to add one, '
                'or run the discovery scraper to populate this automatically.</div>',
                unsafe_allow_html=True,
            )

# =======================================================================
# CAMPAIGNS
# =======================================================================
elif page == "Campaigns":
    st.markdown('<div class="section-label">Create a Campaign</div>', unsafe_allow_html=True)
    with st.container(border=True):
        with st.form("new_campaign_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Campaign name", placeholder="e.g. Plumbing – Texas Q1")
            niche = col2.selectbox("Niche", NICHES)
            col3, col4 = st.columns(2)
            f1_delay = col3.number_input("Follow-up 1 delay (days)", min_value=1, value=1)
            f2_delay = col4.number_input("Follow-up 2 delay (days)", min_value=1, value=1)
            submitted = st.form_submit_button("Create Campaign", type="primary")

            if submitted:
                if not name.strip():
                    st.error("Campaign name is required.")
                else:
                    new_campaign = Campaign(
                        name=name.strip(), niche=niche, status="PAUSED",
                        followup1_delay_days=f1_delay, followup2_delay_days=f2_delay,
                    )
                    session.add(new_campaign)
                    session.commit()
                    st.success(f"Campaign '{name}' created (starts PAUSED — activate below when ready).")
                    st.rerun()

    st.write("")
    st.markdown('<div class="section-label">Your Campaigns</div>', unsafe_allow_html=True)

    campaigns = session.query(Campaign).order_by(Campaign.created_at.desc()).all()

    if not campaigns:
        st.markdown(
            '<div class="empty-state">No campaigns yet — create your first one above.</div>',
            unsafe_allow_html=True,
        )

    for campaign in campaigns:
        with st.container(border=True):
            header_col, badge_col, btn_col1, btn_col2 = st.columns([4, 1.2, 1, 1])
            header_col.markdown(f"**{campaign.name}**  ·  {campaign.niche}")
            badge_col.markdown(status_badge(campaign.status), unsafe_allow_html=True)

            if campaign.status == "ACTIVE":
                if btn_col1.button("Pause", key=f"pause_{campaign.id}"):
                    campaign.status = "PAUSED"
                    session.commit()
                    st.rerun()
            else:
                if btn_col1.button("Activate", key=f"activate_{campaign.id}", type="primary"):
                    campaign.status = "ACTIVE"
                    session.commit()
                    st.rerun()

            with st.expander("Follow-up timing & templates"):
                st.caption(
                    f"Follow-up 1: {campaign.followup1_delay_days} day(s) after initial send · "
                    f"Follow-up 2: {campaign.followup2_delay_days} day(s) after follow-up 1"
                )

                st.markdown("**Email Templates**")
                st.caption(
                    "Write your own offer/pitch/CTA below. Approved variables (auto-filled per lead): "
                    + ", ".join(f"`{{{v}}}`" for v in AVAILABLE_VARIABLES)
                )
                st.caption("⚠️ {first_name} already includes the full greeting (e.g. 'Hi John,') — don't add 'Hi' before it in your template.")

                variant = st.selectbox(
                    "Template variant", TEMPLATE_VARIANTS, key=f"variant_{campaign.id}"
                )

                existing = get_latest_template(campaign.id, variant)
                default_body = existing.body if existing else ""

                body = st.text_area(
                    "Email body",
                    value=default_body,
                    height=200,
                    key=f"body_{campaign.id}_{variant}",
                    placeholder=(
                        "{first_name}\n\n"
                        "I noticed {business_name} in {city}, {state} might be missing "
                        "the Meta Pixel on your website. {website_observation}\n\n"
                        "Want a free trial? Just reply."
                    ),
                )

                save_col, info_col = st.columns([1, 3])
                if save_col.button("Save as new version", key=f"save_{campaign.id}_{variant}"):
                    if not body.strip():
                        st.error("Template body can't be empty.")
                    else:
                        new_template = CampaignTemplate(
                            campaign_id=campaign.id, variant=variant, body=body,
                        )
                        session.add(new_template)
                        session.commit()
                        st.success(f"Saved new version of '{variant}'. Past sends still reference the old version.")
                        st.rerun()

                if existing:
                    info_col.caption(f"Current version last updated: {existing.updated_at.strftime('%b %d, %Y %H:%M')}")

                past_versions = (
                    session.query(CampaignTemplate)
                    .filter(CampaignTemplate.campaign_id == campaign.id, CampaignTemplate.variant == variant)
                    .order_by(CampaignTemplate.updated_at.desc())
                    .all()
                )
                if len(past_versions) > 1:
                    with st.expander(f"Version history ({len(past_versions)})"):
                        for v in past_versions:
                            st.text(f"{v.updated_at.strftime('%b %d, %Y %H:%M')}")
                            st.code(v.body, language=None)

# =======================================================================
# LEADS
# =======================================================================
elif page == "Leads":
    st.markdown('<div class="section-label">Add a Lead Manually</div>', unsafe_allow_html=True)
    with st.expander("+ Add lead"):
        with st.form("add_lead_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            business_name = col1.text_input("Business name")
            niche = col2.selectbox("Niche", NICHES, key="add_lead_niche")
            city = col3.text_input("City")
            col4, col5, col6 = st.columns(3)
            state = col4.text_input("State (2-letter)")
            website = col5.text_input("Website")
            email = col6.text_input("Email")

            submitted = st.form_submit_button("Add Lead", type="primary")
            if submitted:
                if not business_name.strip():
                    st.error("Business name is required.")
                else:
                    lead = Lead(
                        business_name=business_name.strip(), niche=niche,
                        city=city or None, state=state or None,
                        website=website or None, email=email or None,
                        source="manual",
                    )
                    session.add(lead)
                    session.commit()
                    st.success(f"Added '{business_name}'.")
                    st.rerun()

    st.write("")
    st.markdown('<div class="section-label">Search Leads</div>', unsafe_allow_html=True)
    query = st.text_input(
        "Search", placeholder="Search by business name, email, or website…",
        label_visibility="collapsed",
    )
    show_no_email_only = st.checkbox("Show only leads with no email found (need manual follow-up)")

    if query:
        results = (
            session.query(Lead)
            .filter(
                (Lead.business_name.ilike(f"%{query}%"))
                | (Lead.email.ilike(f"%{query}%"))
                | (Lead.website.ilike(f"%{query}%"))
            )
            .all()
        )
    else:
        results = session.query(Lead).order_by(Lead.created_at.desc()).limit(100).all()

    if show_no_email_only:
        results = [l for l in results if l.status == "RESEARCHED" and not l.email]

    if not results:
        st.markdown(
            '<div class="empty-state">No leads match that search.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"{len(results)} lead(s)" + (" (showing latest 100)" if not query else ""))

        table_rows = [
            {
                "Business": l.business_name, "Niche": l.niche, "City": l.city or "—",
                "State": l.state or "—", "Status": l.status, "Email": l.email or "—",
            }
            for l in results
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        st.write("")
        st.markdown('<div class="section-label">Lead Detail</div>', unsafe_allow_html=True)
        selected_name = st.selectbox(
            "Select a lead to view full research + history",
            [f"{l.business_name} (#{l.id})" for l in results],
        )
        selected_lead = next(l for l in results if f"{l.business_name} (#{l.id})" == selected_name)

        with st.container(border=True):
            col1, col2 = st.columns(2)
            col1.markdown(f"**{selected_lead.business_name}**")
            col2.markdown(status_badge(selected_lead.status), unsafe_allow_html=True)

            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.write(f"**City/State:** {selected_lead.city or '—'}, {selected_lead.state or '—'}")
                st.write(f"**Website:** {selected_lead.website or '—'}")
                st.write(f"**Email:** {selected_lead.email or '—'} ({selected_lead.email_status})")
                st.write(f"**Contact name:** {selected_lead.contact_name or 'Unknown (using fallback greeting)'}")
            with info_col2:
                if selected_lead.research:
                    r = selected_lead.research
                    st.write(f"**Meta Pixel:** {r.meta_pixel or 'UNKNOWN'}")
                    st.write(f"**Google Analytics:** {'PRESENT' if r.google_analytics else 'MISSING' if r.google_analytics is not None else 'UNKNOWN'}")
                    st.write(f"**GTM:** {'PRESENT' if r.gtm else 'MISSING' if r.gtm is not None else 'UNKNOWN'}")
                else:
                    st.write("**Research:** Not yet researched.")

            events = (
                session.query(EmailEvent)
                .filter(EmailEvent.lead_id == selected_lead.id)
                .order_by(EmailEvent.scheduled_for)
                .all()
            )
            if events:
                st.write("**Outreach history:**")
                for e in events:
                    when = e.sent_at.strftime("%b %d, %Y %H:%M") if e.sent_at else "pending"
                    st.write(f"- `{e.event_type}` — {when}")
            else:
                st.caption("No outreach history yet.")

# =======================================================================
# SENDER ACCOUNTS
# =======================================================================
elif page == "Sender Accounts":
    st.markdown('<div class="section-label">Add Sender Account</div>', unsafe_allow_html=True)
    with st.expander("+ Add account"):
        with st.form("add_sender_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            acc_email = col1.text_input("Email address")
            provider = col2.selectbox("Provider", ["gmail", "proton"])
            daily_limit = col3.number_input("Daily limit", min_value=1, value=50)
            submitted = st.form_submit_button("Add Account", type="primary")
            if submitted:
                if not acc_email.strip():
                    st.error("Email is required.")
                else:
                    account = SenderAccount(email=acc_email.strip(), provider=provider, daily_limit=daily_limit)
                    session.add(account)
                    session.commit()
                    st.success(f"Added {acc_email}.")
                    st.rerun()

    st.write("")
    st.markdown('<div class="section-label">Accounts</div>', unsafe_allow_html=True)
    accounts = session.query(SenderAccount).all()

    if not accounts:
        st.markdown('<div class="empty-state">No sender accounts yet.</div>', unsafe_allow_html=True)

    for acc in accounts:
        capacity = compute_capacity(acc)
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1.5, 2])
            col1.markdown(f"**{acc.email}**  ·  {acc.provider}")
            col2.markdown(status_badge(capacity.recommended_status), unsafe_allow_html=True)
            col3.write(f"Available today: **{capacity.available_capacity}** / {acc.daily_limit}")
            st.caption(
                f"Sent today: {acc.sent_today} · Bounces (7d): {acc.bounce_count_7d} · "
                f"Complaints (7d): {acc.spam_complaint_count_7d} · Reason: {capacity.reason}"
            )

# =======================================================================
# SUPPRESSION LIST
# =======================================================================
elif page == "Suppression List":
    st.markdown('<div class="section-label">Add Suppression</div>', unsafe_allow_html=True)
    with st.expander("+ Add manually"):
        with st.form("add_suppression_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            supp_email = col1.text_input("Email address")
            reason = col2.selectbox("Reason", ["unsubscribe", "manual", "bounce_hard"])
            permanent = col3.checkbox("Permanent", value=True)
            submitted = st.form_submit_button("Add", type="primary")
            if submitted:
                if not supp_email.strip():
                    st.error("Email is required.")
                else:
                    record = SuppressionList(email=supp_email.strip(), reason=reason, permanent=permanent)
                    session.add(record)
                    session.commit()
                    st.success(f"Suppressed {supp_email}.")
                    st.rerun()

    st.write("")
    st.markdown('<div class="section-label">Suppressed Contacts</div>', unsafe_allow_html=True)
    records = session.query(SuppressionList).order_by(SuppressionList.added_at.desc()).all()

    if not records:
        st.markdown('<div class="empty-state">No suppressed contacts yet.</div>', unsafe_allow_html=True)
    else:
        table_rows = [
            {
                "Email": r.email, "Reason": r.reason,
                "Permanent": "Yes" if r.permanent else "No (90-day cooldown)",
                "Added": r.added_at.strftime("%b %d, %Y"),
            }
            for r in records
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

session.close()