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
from src.core.config import load_settings, save_settings, get_app_mode, set_app_mode
from app.run_agent import run_pipeline_captured
from src.replies.reply_detector import check_all_active_campaigns_captured
from src.email.scheduler import get_due_actions

init_db()

st.set_page_config(
    page_title="AI Outreach Agent",
    page_icon="📬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =======================================================================
# THEME — design system
# =======================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', -apple-system, sans-serif; }

:root {
    --ink: #12161F;
    --body-text: #333B4D;
    --muted-text: #626B80;
    --accent: #E85D2F;
    --accent-dark: #C8481F;
    --accent-soft: #FDEDE6;
    --success: #1E8A4C;
    --success-soft: #E4F5EA;
    --warn: #C24A1E;
    --warn-soft: #FDEDE6;
    --border: #E2E5EC;
    --border-strong: #C9CEDA;
    --bg-page: #F4F5F9;
    --bg-card: #FFFFFF;
    --bg-sidebar: #12161F;
}

/* ---- Page background ---- */
.stApp { background-color: var(--bg-page); }

/* ---- Kill Streamlit's rerun/dimming effect on the whole page ---- */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
.main .block-container,
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"] {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
}
.stApp[data-teststatus="running"] * { opacity: 1 !important; }

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background-color: var(--bg-sidebar);
    border-right: 1px solid #1E2430;
}
section[data-testid="stSidebar"] * { color: #E8EAF0 !important; }
section[data-testid="stSidebar"] .stRadio > label { display: none; }
section[data-testid="stSidebar"] [data-baseweb="radio"] {
    padding: 9px 12px;
    border-radius: 8px;
    margin-bottom: 2px;
    transition: background-color 0.12s ease;
}
section[data-testid="stSidebar"] [data-baseweb="radio"]:hover {
    background-color: rgba(232, 93, 47, 0.14);
}
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] p {
    color: #8A93A8 !important;
}

/* ---- Headings & text: strong contrast everywhere ---- */
h1, h2, h3, h4 { color: var(--ink) !important; font-weight: 800 !important; letter-spacing: -0.01em; }
p, span, label, div { color: var(--body-text); }
.stMarkdown p { color: var(--body-text); }
.stCaption, [data-testid="stCaptionContainer"] p { color: var(--muted-text) !important; font-size: 13px !important; }

/* ---- Hero header ---- */
.hero {
    padding: 6px 0 20px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.hero-title {
    font-size: 32px; font-weight: 800; color: var(--ink); margin: 0;
    letter-spacing: -0.02em;
}
.hero-sub { font-size: 15px; color: var(--muted-text); margin-top: 6px; font-weight: 500; }

/* ---- Section labels (small uppercase headers) ---- */
.section-label {
    font-size: 12.5px; font-weight: 700; color: var(--ink);
    text-transform: uppercase; letter-spacing: 0.07em; margin: 4px 0 10px 0;
    display: flex; align-items: center; gap: 6px;
}

/* ---- Badges ---- */
.badge {
    display: inline-block; padding: 4px 12px; border-radius: 999px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.02em;
}
.badge-active { background: var(--success-soft); color: var(--success); }
.badge-paused { background: #EEF0F5; color: var(--muted-text); }
.badge-warn { background: var(--warn-soft); color: var(--warn); }

/* ---- Metric cards ---- */
div[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(18,22,31,0.04);
}
div[data-testid="stMetricLabel"] { color: var(--muted-text) !important; font-weight: 600 !important; font-size: 13px !important; }
div[data-testid="stMetricValue"] { color: var(--ink) !important; font-weight: 800 !important; }

/* ---- Containers (cards) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-card) !important;
    box-shadow: 0 1px 3px rgba(18,22,31,0.05);
}

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 9px; font-weight: 700; border: 1px solid var(--border-strong);
    color: var(--ink); padding: 8px 18px;
}
.stButton > button:hover { border-color: var(--accent); color: var(--accent-dark); }
.stButton > button[kind="primary"] {
    background-color: var(--accent); border-color: var(--accent); color: #FFFFFF;
}
.stButton > button[kind="primary"]:hover { background-color: var(--accent-dark); color: #FFFFFF; }

/* ---- Text inputs / search / selects: strong visible labels + placeholders ---- */
.stTextInput label, .stSelectbox label, .stNumberInput label, .stCheckbox label p {
    color: var(--ink) !important; font-weight: 600 !important; font-size: 13.5px !important;
}
.stTextInput input, .stNumberInput input {
    color: var(--ink) !important;
    background-color: #FBFBFD !important;
    border: 1.5px solid var(--border-strong) !important;
    border-radius: 9px !important;
}
.stTextInput input::placeholder {
    color: #8A93A8 !important;
    opacity: 1 !important;
    font-weight: 500;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
div[data-baseweb="select"] > div {
    background-color: #FBFBFD !important;
    border: 1.5px solid var(--border-strong) !important;
    border-radius: 9px !important;
    color: var(--ink) !important;
}

/* ---- Code / log output box ---- */
.stCodeBlock, pre {
    background-color: #12161F !important;
    border-radius: 10px !important;
    border: 1px solid #1E2430 !important;
}
.stCodeBlock code, pre code { color: #E8EAF0 !important; font-size: 13px !important; }

/* ---- Dataframe ---- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}

/* ---- Alerts ---- */
div[data-testid="stAlert"] { border-radius: 10px; font-weight: 500; }

/* ---- Empty state ---- */
.empty-state {
    border: 1.5px dashed var(--border-strong); border-radius: 14px;
    padding: 40px 24px; text-align: center; color: var(--muted-text);
    background: var(--bg-card); font-size: 14.5px; font-weight: 500;
}

/* ---- Expander ---- */
details {
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    background: var(--bg-card) !important;
}
summary { font-weight: 700 !important; color: var(--ink) !important; }

/* ---- Divider spacing tighten ---- */
hr { margin: 8px 0 !important; border-color: var(--border) !important; }
/* ---- Force all links (emails, business names in tables) to dark, readable text ---- */
a, a:link, a:visited {
    color: var(--ink) !important;
    text-decoration: none !important;
    font-weight: 600 !important;
}
a:hover { color: var(--accent) !important; text-decoration: underline !important; }

/* ---- Dataframe cell text: force dark ---- */
[data-testid="stDataFrame"] * {
    color: var(--body-text) !important;
}
[data-testid="stDataFrame"] [role="columnheader"] {
    color: var(--ink) !important;
    font-weight: 700 !important;
}

/* ---- Captions: darker than before, still distinguishable from body text ---- */
.stCaption, [data-testid="stCaptionContainer"] p {
    color: #4A5266 !important;
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

NAV_ITEMS = {
    "Overview": "📊 Overview",
    "Operations": "⚙️ Operations",
    "Campaigns": "📣 Campaigns",
    "Leads": "🧾 Leads",
    "Sender Accounts": "✉️ Sender Accounts",
    "Suppression List": "🚫 Suppression List",
}


def status_badge(status: str) -> str:
    mapping = {"ACTIVE": "badge-active", "PAUSED": "badge-paused", "THROTTLED": "badge-warn"}
    css_class = mapping.get(status, "badge-paused")
    return f'<span class="badge {css_class}">{status}</span>'


def section_header(icon: str, text: str):
    st.markdown(f'<div class="section-label">{text}</div>', unsafe_allow_html=True)


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
    st.markdown(
        "<div style='padding:6px 4px 18px 4px;'>"
        "<div style='font-size:20px;font-weight:800;color:#FFFFFF;'>📬 Outreach Agent</div>"
        "<div style='font-size:12.5px;color:#8A93A8;margin-top:2px;'>AI-assisted home services outreach</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    page_label = st.radio(
        "Navigate", list(NAV_ITEMS.values()), label_visibility="collapsed",
    )
    page = [k for k, v in NAV_ITEMS.items() if v == page_label][0]
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
    suppressed = session.query(SuppressionList).count()
    
    reply_events = session.query(EmailEvent).filter(EmailEvent.event_type == "REPLY").all()
    reply_categories = {}
    for e in reply_events:
        if e.notes and "category=" in e.notes:
            cat = e.notes.split("category=")[1].strip()
            reply_categories[cat] = reply_categories.get(cat, 0) + 1

    total_daily_capacity = sum(
        acc.daily_limit for acc in session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Leads Discovered", total_leads)
    c2.metric("Researched", researched)
    c3.metric("Emails Sent Today", f"{sent_today} / {total_daily_capacity}")
    c4.metric("Replies", replies)
    c5.metric("Suppressed", suppressed)

    st.write("")
    section_header("📈", "Leads by Status")

    status_counts = dict(
        session.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all()
    )
    with st.container(border=True):
        if status_counts:
            st.bar_chart(status_counts, color="#E85D2F")
        else:
            st.markdown(
                '<div class="empty-state">No leads yet. Head to the <b>Leads</b> tab to add one, '
                'or run the pipeline from <b>Operations</b> to populate this automatically.</div>',
                unsafe_allow_html=True,
            )

    if reply_categories:
        st.write("")
        section_header("", "Reply Breakdown")
        with st.container(border=True):
            cols = st.columns(len(reply_categories))
            for col, (cat, count) in zip(cols, reply_categories.items()):
                col.metric(cat.replace("_", " ").title(), count)

# =======================================================================
# OPERATIONS
# =======================================================================
elif page == "Operations":
    settings = load_settings()

    section_header("🟢", "Sending Mode")
    with st.container(border=True):
        current_mode = get_app_mode()
        col1, col2 = st.columns([2, 1])
        if current_mode == "TEST":
            col1.markdown(
                "Currently in **TEST** mode. All emails go to your own inbox — never real prospects."
            )
            if col2.button("Switch to PRODUCTION", type="primary"):
                set_app_mode("PRODUCTION")
                st.success("Switched to PRODUCTION. Real emails will now be sent.")
                st.rerun()
        else:
            col1.markdown("⚠️ Currently in **PRODUCTION** mode. Emails go to **real prospects**.")
            if col2.button("Switch to TEST"):
                set_app_mode("TEST")
                st.success("Switched to TEST. Emails will go to your own inbox only.")
                st.rerun()

    st.write("")
    section_header("📅", "Today's Forecast")
    with st.container(border=True):
        all_campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()
        total_followups_due = 0
        for c in all_campaigns:
            due = get_due_actions(session, c)
            total_followups_due += sum(1 for a in due if a.action_type in ("FOLLOWUP1", "FOLLOWUP2"))

        active_accounts = session.query(SenderAccount).filter(SenderAccount.status == "ACTIVE").all()
        total_capacity = sum(acc.daily_limit for acc in active_accounts)
        already_sent = sum(acc.sent_today for acc in active_accounts)
        remaining_today = max(0, total_capacity - already_sent)
        room_for_new_leads = max(0, remaining_today - total_followups_due)

        fc1, fc2, fc3 = st.columns(3)
        fc1.metric("Follow-ups due today", total_followups_due)
        fc2.metric("Remaining capacity today", remaining_today)
        fc3.metric("Room for new leads", room_for_new_leads)

        if room_for_new_leads <= 0:
            st.warning(
                "No room left for new leads today — follow-ups alone will use your full capacity. "
                "Skip discovering a new city today, or just run replies/follow-ups."
            )
        elif room_for_new_leads < 10:
            st.info(f"Only {room_for_new_leads} slot(s) left for new leads today — a small city or a partial batch will fit.")
        else:
            st.success(f"You have room for up to {room_for_new_leads} new leads today after follow-ups are handled.")

    st.write("")
    section_header("▶️", "Run Pipeline")
    with st.container(border=True):
        st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">Discovers leads, researches them, queues eligible ones, and sends due emails — all in one click.</p>', unsafe_allow_html=True)

        cities = settings.get("target_cities", [{"city": "Austin", "state": "TX"}])
        city_options = [f"{c['city']}, {c['state']}" for c in cities]

        col1, col2 = st.columns(2)
        niche_choice = col1.selectbox("Niche", NICHES, key="run_niche")
        city_choice = col2.selectbox(
            "City", sorted(city_options), key="run_city",
            help="Click and type to search — matches anywhere in the city name.",
        )

        active_campaigns = session.query(Campaign).filter(Campaign.status == "ACTIVE").all()
        campaign_options = ["Auto-select by niche"] + [f"{c.name} (#{c.id})" for c in active_campaigns]
        campaign_choice = st.selectbox("Campaign (optional)", campaign_options, key="run_campaign")

        selected_campaign_id = None
        if campaign_choice != "Auto-select by niche":
            selected_campaign_id = int(campaign_choice.split("#")[1].rstrip(")"))

        run_clicked = st.button("▶ Run Pipeline Now", type="primary")

        if run_clicked:
            city_name, state_name = city_choice.split(", ")
            with st.spinner("Running discovery → research → queue → send..."):
                log = run_pipeline_captured(niche_choice, city_name, state_name, selected_campaign_id)
            st.markdown("**Result:**")
            st.code(log, language=None)

    st.write("")
    section_header("✉️", "Check for Replies")
    with st.container(border=True):
        st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">Checks your inbox for new replies, matches them to leads, and stops follow-ups automatically.</p>', unsafe_allow_html=True)
        if st.button("✉ Check Replies Now"):
            with st.spinner("Checking inbox..."):
                log = check_all_active_campaigns_captured()
            st.markdown("**Result:**")
            st.code(log, language=None)

    st.write("")
    section_header("🕘", "Sending Window")
    with st.container(border=True):
        st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">Emails only send within this local-time window for the prospect\'s own US timezone.</p>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        start_hour = col1.number_input(
            "Start hour (24h)", min_value=0, max_value=23,
            value=settings["sending_window"]["start_hour"],
        )
        end_hour = col2.number_input(
            "End hour (24h)", min_value=1, max_value=24,
            value=settings["sending_window"]["end_hour"],
        )
        if st.button("Save Sending Window"):
            settings["sending_window"] = {"start_hour": start_hour, "end_hour": end_hour}
            save_settings(settings)
            st.success("Sending window updated.")

    st.write("")
    section_header("🌙", "Your Quiet Hours (for reply acknowledgements)")
    with st.container(border=True):
        st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">If a reply comes in during these hours (your own local time), a brief \'I\'ll get back to you\' note is sent automatically.</p>', unsafe_allow_html=True)
        quiet = settings.get("your_quiet_hours", {"start_hour": 23, "end_hour": 8, "timezone": "Asia/Karachi"})
        col1, col2, col3 = st.columns(3)
        q_start = col1.number_input("Quiet hours start", min_value=0, max_value=23, value=quiet["start_hour"])
        q_end = col2.number_input("Quiet hours end", min_value=0, max_value=23, value=quiet["end_hour"])
        q_tz = col3.text_input("Your timezone", value=quiet.get("timezone", "Asia/Karachi"))
        if st.button("Save Quiet Hours"):
            settings["your_quiet_hours"] = {"start_hour": q_start, "end_hour": q_end, "timezone": q_tz}
            save_settings(settings)
            st.success("Quiet hours updated.")

    st.write("")
    section_header("🌎", "Target Cities")
    with st.container(border=True):
        st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">Cities the pipeline discovers leads in. Add as many as you want across the US.</p>', unsafe_allow_html=True)
        for i, c in enumerate(cities):
            col1, col2 = st.columns([4, 1])
            col1.write(f"📍 {c['city']}, {c['state']}")
            if col2.button("Remove", key=f"remove_city_{i}"):
                cities.pop(i)
                settings["target_cities"] = cities
                save_settings(settings)
                st.rerun()

        st.write("")
        col1, col2, col3 = st.columns([2, 1, 1])
        new_city = col1.text_input("City name", key="new_city_input", placeholder="e.g. Phoenix")
        new_state = col2.text_input("State code", key="new_state_input", placeholder="e.g. AZ")
        col3.write("")
        col3.write("")
        if col3.button("+ Add City"):
            if new_city.strip() and new_state.strip():
                cities.append({"city": new_city.strip(), "state": new_state.strip().upper()})
                settings["target_cities"] = cities
                save_settings(settings)
                st.rerun()

# =======================================================================
# CAMPAIGNS
# =======================================================================
elif page == "Campaigns":
    section_header("➕", "Create a Campaign")
    with st.container(border=True):
        with st.form("new_campaign_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Campaign name", placeholder="e.g. Plumbing – Texas Q1")
            niche = col2.selectbox("Niche", NICHES)
            col3, col4 = st.columns(2)
            f1_delay = col3.number_input("Follow-up 1 delay (days)", min_value=1, value=1)
            f2_delay = col4.number_input("Follow-up 2 delay (days)", min_value=1, value=1)
            f2_enabled = st.checkbox("Send follow-up 2", value=True)
            submitted = st.form_submit_button("Create Campaign", type="primary")

            if submitted:
                if not name.strip():
                    st.error("Campaign name is required.")
                else:
                    new_campaign = Campaign(
                        name=name.strip(), niche=niche, status="PAUSED",
                        followup1_delay_days=f1_delay, followup2_delay_days=f2_delay,
                        followup2_enabled=f2_enabled,
                    )
                    session.add(new_campaign)
                    session.commit()
                    st.success(f"Campaign '{name}' created (starts PAUSED — activate below when ready).")
                    st.rerun()

    st.write("")
    section_header("📣", "Your Campaigns")

    campaigns = session.query(Campaign).order_by(Campaign.created_at.desc()).all()

    if not campaigns:
        st.markdown('<div class="empty-state">No campaigns yet — create your first one above.</div>', unsafe_allow_html=True)

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

            delete_confirm_key = f"confirm_delete_{campaign.id}"
            if btn_col2.button("Delete", key=f"delete_{campaign.id}"):
                st.session_state[delete_confirm_key] = True

            if st.session_state.get(delete_confirm_key):
                st.warning(
                    f"Delete '{campaign.name}'? This also deletes its templates and email history. "
                    "This cannot be undone."
                )
                confirm_col1, confirm_col2 = st.columns(2)
                if confirm_col1.button("Yes, delete permanently", key=f"confirm_yes_{campaign.id}", type="primary"):
                    session.delete(campaign)
                    session.commit()
                    del st.session_state[delete_confirm_key]
                    st.rerun()
                if confirm_col2.button("Cancel", key=f"confirm_no_{campaign.id}"):
                    del st.session_state[delete_confirm_key]
                    st.rerun()

            with st.expander("📝 Follow-up timing & templates"):
                st.caption(
                    f"Follow-up 1: {campaign.followup1_delay_days} day(s) after initial send · "
                    f"Follow-up 2: {campaign.followup2_delay_days} day(s) after follow-up 1"
                )

                followup2_toggle = st.checkbox(
                    "Send follow-up 2", value=campaign.followup2_enabled, key=f"f2_toggle_{campaign.id}",
                )
                if followup2_toggle != campaign.followup2_enabled:
                    campaign.followup2_enabled = followup2_toggle
                    session.commit()
                    st.rerun()
                    
                delay_col1, delay_col2, delay_col3 = st.columns([1, 1, 1])
                new_f1_delay = delay_col1.number_input(
                    "Follow-up 1 delay (days)", min_value=1, value=campaign.followup1_delay_days,
                    key=f"f1_delay_{campaign.id}",
                )
                new_f2_delay = delay_col2.number_input(
                    "Follow-up 2 delay (days)", min_value=1, value=campaign.followup2_delay_days,
                    key=f"f2_delay_{campaign.id}",
                )
                delay_col3.write("")
                delay_col3.write("")
                if delay_col3.button("Update delays", key=f"update_delays_{campaign.id}"):
                    campaign.followup1_delay_days = new_f1_delay
                    campaign.followup2_delay_days = new_f2_delay
                    session.commit()
                    st.success("Follow-up delays updated.")
                    st.rerun()

                st.markdown("**Email Templates**")
                st.caption(
                    "Write your own offer/pitch/CTA below. Approved variables (auto-filled per lead): "
                    + ", ".join(f"`{{{v}}}`" for v in AVAILABLE_VARIABLES)
                )
                st.caption(
                    "⚠️ {first_name} already includes the full greeting (e.g. 'Hi John,') — "
                    "don't add 'Hi' before it in your template."
                )

                variant = st.selectbox("Template variant", TEMPLATE_VARIANTS, key=f"variant_{campaign.id}")

                existing = get_latest_template(campaign.id, variant)
                default_body = existing.body if existing else ""

                body = st.text_area(
                    "Email body", value=default_body, height=200,
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
                        new_template = CampaignTemplate(campaign_id=campaign.id, variant=variant, body=body)
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
    section_header("", "Add a Lead Manually")
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
    section_header("", "Search Leads")
    query = st.text_input(
        "Search Leads", placeholder="Search by business name, email, or website…",
    )

    filter_col1, filter_col2 = st.columns(2)
    all_niches_in_db = [n[0] for n in session.query(Lead.niche).distinct().all()]
    all_cities_in_db = sorted(set(c[0] for c in session.query(Lead.city).filter(Lead.city.isnot(None)).distinct().all()))

    niche_filter = filter_col1.selectbox("Filter by niche", ["All niches"] + all_niches_in_db, key="leads_niche_filter")
    city_filter = filter_col2.selectbox("Filter by city", ["All cities"] + all_cities_in_db, key="leads_city_filter")

    st.write("")
    tab_has_email, tab_manual = st.tabs(["Has Email (auto-outreach)", "Manual Review (no email found)"])

    def render_lead_table_and_detail(results: list, key_prefix: str):
        if not results:
            st.markdown('<div class="empty-state">No leads match here.</div>', unsafe_allow_html=True)
            return

        st.markdown(
            f'<p style="color:#2A3142;font-weight:500;font-size:14px;">{len(results)} lead(s)</p>',
            unsafe_allow_html=True,
        )

        table_rows = [
            {
                "Business": l.business_name, "Niche": l.niche, "City": l.city or "—",
                "State": l.state or "—", "Status": l.status,
                "Email": l.email or "—", "Phone": l.phone or "—",
            }
            for l in results
        ]
        table_selection = st.dataframe(
            table_rows, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row", key=f"leads_table_{key_prefix}",
        )

        st.write("")
        section_header("", "Lead Detail")

        selected_rows = table_selection.selection.rows
        if selected_rows:
            selected_lead = results[selected_rows[0]]
            st.markdown(
                f'<p style="color:#2A3142;font-weight:500;font-size:14px;">Showing: <b>{selected_lead.business_name}</b> — click another row above to switch.</p>',
                unsafe_allow_html=True,
            )
        else:
            selected_name = st.selectbox(
                "Or pick a lead here",
                [f"{l.business_name} (#{l.id})" for l in results],
                key=f"select_{key_prefix}",
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
                st.write(f"**Phone:** {selected_lead.phone or '—'}")
                st.write(f"**Contact name:** {selected_lead.contact_name or 'Unknown (using fallback greeting)'}")
            with info_col2:
                if selected_lead.research:
                    r = selected_lead.research
                    st.write(f"**Meta Pixel:** {r.meta_pixel or 'UNKNOWN'}")
                    st.write(
                        f"**Google Analytics:** "
                        f"{'PRESENT' if r.google_analytics else 'MISSING' if r.google_analytics is not None else 'UNKNOWN'}"
                    )
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
                st.markdown('<p style="color:#2A3142;font-weight:500;font-size:14px;">No outreach history yet.</p>', unsafe_allow_html=True)

    if query:
        base_query = (
            session.query(Lead)
            .filter(
                (Lead.business_name.ilike(f"%{query}%"))
                | (Lead.email.ilike(f"%{query}%"))
                | (Lead.website.ilike(f"%{query}%"))
            )
        )
    else:
        base_query = session.query(Lead)

    if niche_filter != "All niches":
        base_query = base_query.filter(Lead.niche == niche_filter)
    if city_filter != "All cities":
        base_query = base_query.filter(Lead.city == city_filter)

    all_matching = base_query.order_by(Lead.created_at.desc()).all()

    with tab_has_email:
        has_email_results = [l for l in all_matching if l.email]
        render_lead_table_and_detail(has_email_results, "has_email")

    with tab_manual:
        manual_results = [l for l in all_matching if not l.email]
        render_lead_table_and_detail(manual_results, "manual")
        
# =======================================================================
# SENDER ACCOUNTS
# =======================================================================
elif page == "Sender Accounts":
    section_header("➕", "Add Sender Account")
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
    section_header("✉️", "Accounts")
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
            st.markdown(
                f'<p style="color:#2A3142;font-weight:500;font-size:14px;">'
                f"Sent today: {acc.sent_today} · Bounces (7d): {acc.bounce_count_7d} · "
                f"Complaints (7d): {acc.spam_complaint_count_7d} · Reason: {capacity.reason}"
                '</p>',
                unsafe_allow_html=True,
            )
            edit_col1, edit_col2 = st.columns([3, 1])
            new_limit = edit_col1.number_input(
                "Daily email limit", min_value=1, value=acc.daily_limit, key=f"limit_{acc.id}"
            )
            if edit_col2.button("Update", key=f"update_limit_{acc.id}"):
                acc.daily_limit = new_limit
                session.commit()
                st.success(f"Daily limit updated to {new_limit}.")
                st.rerun()

# =======================================================================
# SUPPRESSION LIST
# =======================================================================
elif page == "Suppression List":
    section_header("➕", "Add Suppression")
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
    section_header("🚫", "Suppressed Contacts")
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