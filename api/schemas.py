"""
Pydantic response/request shapes for the API. These are deliberately
thin — they mirror the ORM models in src/db/models.py, not a separate
design.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class LeadOut(BaseModel):
    id: int
    business_name: str
    niche: str
    city: Optional[str] = None
    state: Optional[str] = None
    status: str
    email: Optional[str] = None
    email_status: str
    phone: Optional[str] = None
    contact_name: Optional[str] = None
    website: Optional[str] = None
    meta_pixel: Optional[str] = None
    google_analytics: Optional[str] = None
    gtm: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignOut(BaseModel):
    id: int
    name: str
    niche: str
    status: str
    followup1_delay_days: int
    followup2_delay_days: int
    followup2_enabled: bool
    target_state: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    niche: str
    followup1_delay_days: int = 1
    followup2_delay_days: int = 1
    followup2_enabled: bool = True


class CampaignStatusUpdate(BaseModel):
    status: str  # ACTIVE / PAUSED


class SenderAccountOut(BaseModel):
    id: int
    email: str
    provider: str
    daily_limit: int
    sent_today: int
    bounce_count_7d: int
    spam_complaint_count_7d: int
    status: str
    available_capacity: Optional[int] = None
    capacity_reason: Optional[str] = None

    class Config:
        from_attributes = True


class OverviewStats(BaseModel):
    total_leads: int
    researched: int
    sent_today: int
    total_daily_capacity: int
    replies: int
    suppressed: int
    status_counts: dict
    reply_categories: dict


class ForecastStats(BaseModel):
    emails_found_today: int
    pending_unsent: int
    followups_due_today: int
    remaining_capacity_today: int
    room_for_new_leads: int
    needs_manual_review: int
    total_capacity_today: int
    already_sent_today: int


class SendRequest(BaseModel):
    # campaign_id -> how many emails to send for that campaign (same
    # "per-niche limit" idea as the Streamlit Operations tab, just
    # expressed per campaign so the API stays simple).
    campaign_limits: dict[int, int]


class SendJobCreated(BaseModel):
    job_id: str
    total_requested: int


# ---------------------------------------------------------------------
# Phase 1.5 additions
# ---------------------------------------------------------------------

class LeadResearchOut(BaseModel):
    meta_pixel: Optional[str] = None
    google_analytics: Optional[bool] = None
    gtm: Optional[str] = None  # "PRESENT"/"MISSING"/"UNKNOWN" (rendered from bool/None)

    class Config:
        from_attributes = True


class EmailEventOut(BaseModel):
    event_type: str
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LeadDetailOut(LeadOut):
    research: Optional[LeadResearchOut] = None
    events: List[EmailEventOut] = []


class LeadCreate(BaseModel):
    business_name: str
    niche: str
    city: Optional[str] = None
    state: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None


class NicheStat(BaseModel):
    niche: str
    new_pending: int
    followup_pending: int
    sent_today: int


class TemplateOut(BaseModel):
    id: int
    campaign_id: int
    variant: str
    body: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    variant: str
    body: str


class CampaignUpdate(BaseModel):
    followup1_delay_days: Optional[int] = None
    followup2_delay_days: Optional[int] = None
    followup2_enabled: Optional[bool] = None


class SenderAccountCreate(BaseModel):
    email: str
    provider: str
    daily_limit: int = 50


class SenderAccountUpdate(BaseModel):
    daily_limit: int


class SuppressionOut(BaseModel):
    id: int
    email: str
    reason: str
    permanent: bool
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuppressionCreate(BaseModel):
    email: str
    reason: str = "manual"
    permanent: bool = True


class SendingWindow(BaseModel):
    start_hour: int
    end_hour: int


class TargetCity(BaseModel):
    city: str
    state: str


class SettingsOut(BaseModel):
    sending_window: SendingWindow
    target_cities: List[TargetCity]


class PipelineRunRequest(BaseModel):
    niche: str
    city: str
    state: str


class JobCreated(BaseModel):
    job_id: str


class SendByNicheAssignment(BaseModel):
    niche: str
    limit: int
    campaign_ids: List[int]


class SendByNicheRequest(BaseModel):
    assignments: List[SendByNicheAssignment]


class CheckRepliesResult(BaseModel):
    log: str
