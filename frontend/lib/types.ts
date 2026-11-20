// Mirrors api/schemas.py 1:1. If a field changes there, change it here.

export type Mode = "TEST" | "PRODUCTION";

export const NICHES = ["plumbing", "hvac", "roofing", "electrical"] as const;
export type Niche = (typeof NICHES)[number];

export const TEMPLATE_VARIANTS = [
  "pixel_found",
  "pixel_missing",
  "pixel_unknown",
  "followup_1",
  "followup_2",
] as const;
export type TemplateVariant = (typeof TEMPLATE_VARIANTS)[number];

export const TEMPLATE_VARIABLES = [
  "first_name",
  "business_name",
  "city",
  "state",
  "niche",
  "meta_pixel_status",
  "website_observation",
] as const;

export interface Lead {
  id: number;
  business_name: string;
  niche: string;
  city: string | null;
  state: string | null;
  status: string;
  email: string | null;
  email_status: string;
  phone: string | null;
  contact_name: string | null;
  website: string | null;
  meta_pixel: string | null;
  google_analytics: string | null;
  gtm: string | null;
  created_at: string | null;
}

export interface LeadResearch {
  meta_pixel: string | null;
  google_analytics: boolean | null;
  gtm: string | null; // "PRESENT" | "MISSING" | "UNKNOWN"
}

export interface EmailEvent {
  event_type: string;
  scheduled_for: string | null;
  sent_at: string | null;
}

export interface LeadDetail extends Lead {
  research: LeadResearch | null;
  events: EmailEvent[];
}

export interface LeadCreate {
  business_name: string;
  niche: string;
  city?: string | null;
  state?: string | null;
  website?: string | null;
  email?: string | null;
}

export interface LeadFilterOptions {
  niches: string[];
  cities: string[];
  states: string[];
}

export interface NicheStat {
  niche: string;
  new_pending: number;
  followup_pending: number;
  sent_today: number;
}

export interface Campaign {
  id: number;
  name: string;
  niche: string;
  status: "ACTIVE" | "PAUSED" | string;
  followup1_delay_days: number;
  followup2_delay_days: number;
  followup2_enabled: boolean;
  target_state: string | null;
  created_at: string | null;
}

export interface CampaignCreate {
  name: string;
  niche: string;
  followup1_delay_days: number;
  followup2_delay_days: number;
  followup2_enabled: boolean;
}

export interface CampaignUpdate {
  followup1_delay_days?: number;
  followup2_delay_days?: number;
  followup2_enabled?: boolean;
}

export interface Template {
  id: number;
  campaign_id: number;
  variant: string;
  body: string;
  updated_at: string | null;
}

export interface SenderAccount {
  id: number;
  email: string;
  provider: string;
  daily_limit: number;
  sent_today: number;
  bounce_count_7d: number;
  spam_complaint_count_7d: number;
  status: string;
  available_capacity: number | null;
  capacity_reason: string | null;
}

export interface SenderAccountCreate {
  email: string;
  provider: string;
  daily_limit: number;
}

export interface Suppression {
  id: number;
  email: string;
  reason: string;
  permanent: boolean;
  added_at: string | null;
}

export interface SuppressionCreate {
  email: string;
  reason: string;
  permanent: boolean;
}

export interface OverviewStats {
  total_leads: number;
  researched: number;
  sent_today: number;
  total_daily_capacity: number;
  replies: number;
  suppressed: number;
  status_counts: Record<string, number>;
  reply_categories: Record<string, number>;
}

export interface ForecastStats {
  emails_found_today: number;
  pending_unsent: number;
  followups_due_today: number;
  remaining_capacity_today: number;
  room_for_new_leads: number;
  needs_manual_review: number;
  total_capacity_today: number;
  already_sent_today: number;
}

export interface TargetCity {
  city: string;
  state: string;
}

export interface Settings {
  sending_window: { start_hour: number; end_hour: number };
  target_cities: TargetCity[];
}

// --- Background jobs -------------------------------------------------

export interface SendJobCreated {
  job_id: string;
  total_requested: number;
}

export interface SendByNicheAssignment {
  niche: string;
  limit: number;
  campaign_ids: number[];
}

export interface SendSummary {
  sent: number;
  skipped_no_capacity: number;
  skipped_outside_window: number;
  skipped_no_template: number;
  skipped_suppressed: number;
}

export type SendEvent =
  | { type: "heartbeat" }
  | {
      type: "progress";
      sent: number;
      total: number;
      campaign_id: number;
      campaign_name: string;
      niche?: string;
    }
  | {
      type: "done";
      summary: SendSummary;
      per_niche_sent?: Record<string, number>;
      per_campaign_sent?: Record<string, number>;
      total_requested?: number;
    }
  | { type: "error"; message: string };

export interface PipelineJob {
  status: "running" | "done" | "error";
  log: string | null;
  error: string | null;
}
