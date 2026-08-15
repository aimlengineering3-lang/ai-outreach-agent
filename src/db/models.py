"""
SQLAlchemy ORM models — Python classes that map to database tables.

Why this file exists:
Instead of writing raw SQL for every table, we define each table as a
Python class. SQLAlchemy translates class attributes into SQL columns,
and Python objects into database rows, automatically.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    Every ORM model inherits from this. SQLAlchemy uses it to keep track
    of all mapped classes so it knows what tables to create.
    """
    pass


class Lead(Base):
    """
    A single business we've discovered (plumber, HVAC company, etc.)
    This is the central table — almost everything else references it.
    """
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_name: Mapped[str] = mapped_column(String, nullable=False)
    niche: Mapped[str] = mapped_column(String, nullable=False)  # plumbing/hvac/roofing/electrical
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # IANA, e.g. America/Chicago
    website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_status: Mapped[str] = mapped_column(String, default="unknown")  # valid/invalid/unknown
    contact_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # never fabricated
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # google_search/maps/manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String, default="NEW")  # NEW/RESEARCHED/QUEUED/CONTACTED/...

    # One lead has AT MOST one research record. back_populates keeps both
    # sides of the relationship in sync automatically (lead.research and
    # research.lead both work, without you manually setting both).
    research: Mapped[Optional["LeadResearch"]] = relationship(
        back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )

    # One lead can have MANY email events over time (initial + 2 followups).
    email_events: Mapped[List["EmailEvent"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lead id={self.id} business_name={self.business_name!r} status={self.status}>"


class LeadResearch(Base):
    """
    Marketing-technology research collected about a lead's website:
    Meta Pixel, GA, GTM, and factual observations for personalization.
    """
    __tablename__ = "lead_research"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False)
    meta_pixel: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # PRESENT/MISSING/UNKNOWN
    google_analytics: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gtm: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    capi_signal: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # yes/no/unknown
    social_links: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # stored as JSON string
    observations: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # JSON string, LLM-selected facts
    researched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    lead: Mapped["Lead"] = relationship(back_populates="research")

    def __repr__(self) -> str:
        return f"<LeadResearch lead_id={self.lead_id} meta_pixel={self.meta_pixel}>"


class Campaign(Base):
    """
    A named outreach campaign (e.g. "HVAC Q1 push"). Groups templates
    and controls follow-up timing.
    """
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    niche: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PAUSED")  # ACTIVE/PAUSED
    followup1_delay_days: Mapped[int] = mapped_column(Integer, default=1)
    followup2_delay_days: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    templates: Mapped[List["CampaignTemplate"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    email_events: Mapped[List["EmailEvent"]] = relationship(back_populates="campaign")

    def __repr__(self) -> str:
        return f"<Campaign name={self.name!r} status={self.status}>"


class CampaignTemplate(Base):
    """
    A versioned email template. Rows are NEVER edited in place — a template
    change inserts a new row, so email_events can point at the exact
    version that was actually sent (audit trail, per your requirement #16).
    """
    __tablename__ = "campaign_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    variant: Mapped[str] = mapped_column(String, nullable=False)  # pixel_found/pixel_missing/followup1/...
    body: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped["Campaign"] = relationship(back_populates="templates")
    email_events: Mapped[List["EmailEvent"]] = relationship(back_populates="template_used")

    def __repr__(self) -> str:
        return f"<CampaignTemplate variant={self.variant!r} campaign_id={self.campaign_id}>"


class EmailEvent(Base):
    """
    A single email action: the initial send, a followup, a reply, a bounce,
    or an unsubscribe. This table is the permanent audit log — rows are
    never deleted (requirement #21: preserve historical email events).
    """
    __tablename__ = "email_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    sender_account_id: Mapped[int] = mapped_column(ForeignKey("sender_accounts.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)  # SENT/FOLLOWUP1/FOLLOWUP2/REPLY/BOUNCE/UNSUBSCRIBE
    template_used_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaign_templates.id"), nullable=True
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="email_events")
    campaign: Mapped["Campaign"] = relationship(back_populates="email_events")
    template_used: Mapped[Optional["CampaignTemplate"]] = relationship(back_populates="email_events")

    def __repr__(self) -> str:
        return f"<EmailEvent lead_id={self.lead_id} event_type={self.event_type}>"


class SenderAccount(Base):
    """
    An email account we send from (Gmail/Proton). Tracks health so the
    scheduler can compute real available capacity — never a hardcoded number.
    """
    __tablename__ = "sender_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # gmail/proton
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_today: Mapped[int] = mapped_column(Integer, default=0)
    bounce_count_7d: Mapped[int] = mapped_column(Integer, default=0)
    spam_complaint_count_7d: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")  # ACTIVE/THROTTLED/PAUSED
    last_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SenderAccount email={self.email!r} status={self.status}>"


class SuppressionList(Base):
    """
    Permanent or cooldown do-not-contact records. Checked before every send.
    """
    __tablename__ = "suppression_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)  # unsubscribe/manual/bounce_hard
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    permanent: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<SuppressionList email={self.email!r} permanent={self.permanent}>"