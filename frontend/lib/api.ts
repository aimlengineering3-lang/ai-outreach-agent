import type {
  Campaign, CampaignCreate, CampaignUpdate, ForecastStats, Lead, LeadCreate,
  LeadDetail, LeadFilterOptions, Mode, NicheStat, OverviewStats, PipelineJob,
  SendByNicheAssignment, SendJobCreated, SenderAccount, SenderAccountCreate,
  Settings, Suppression, SuppressionCreate, Template,
} from "./types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const hasBody = init.body !== undefined;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      // Only send Content-Type when there is a body. A header on plain GETs
      // would force a CORS preflight request before every single read, and
      // that extra round trip is exactly the kind of lag we're removing.
      headers: hasBody ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Can't reach the API at ${API_URL}. Start it with: uvicorn api.main:app --reload --port 8000`,
      0,
    );
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body?.detail)) {
        message = body.detail
          .map((d: { msg?: string }) => d.msg)
          .filter(Boolean)
          .join("; ");
      }
    } catch {
      /* body wasn't JSON — keep the generic message */
    }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}

const get = <T,>(path: string) => request<T>(path);
const send = <T,>(method: "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown) =>
  request<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

/** WebSocket URL for live send progress (ws:// or wss:// derived from API_URL). */
export function sendProgressUrl(jobId: string) {
  return `${API_URL.replace(/^http/, "ws")}/operations/send/${jobId}/ws`;
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  // Overview
  overview: () => get<OverviewStats>("/overview"),
  forecast: () => get<ForecastStats>("/overview/forecast"),

  // Operations
  getMode: () => get<{ mode: Mode }>("/operations/mode"),
  setMode: (mode: Mode) => send<{ mode: Mode }>("POST", `/operations/mode?mode=${mode}`),
  startSend: (campaign_limits: Record<number, number>) =>
    send<SendJobCreated>("POST", "/operations/send", { campaign_limits }),
  startSendByNiche: (assignments: SendByNicheAssignment[]) =>
    send<SendJobCreated>("POST", "/operations/send-by-niche", { assignments }),
  checkReplies: () => send<{ log: string }>("POST", "/operations/check-replies"),

  // Pipeline
  runPipeline: (niche: string, city: string, state: string) =>
    send<{ job_id: string }>("POST", "/pipeline/run", { niche, city, state }),
  pipelineStatus: (jobId: string) => get<PipelineJob>(`/pipeline/run/${jobId}`),

  // Leads
  leads: (params: {
    search?: string; niche?: string; city?: string; state?: string; has_email?: boolean; limit?: number;
  }) => get<Lead[]>(`/leads${buildQuery(params)}`),
  leadFilterOptions: () => get<LeadFilterOptions>("/leads/filter-options"),
  nicheStats: () => get<NicheStat[]>("/leads/niche-stats"),
  lead: (id: number) => get<LeadDetail>(`/leads/${id}`),
  createLead: (payload: LeadCreate) => send<Lead>("POST", "/leads", payload),

  // Campaigns
  campaigns: (params: { niche?: string; status?: string } = {}) =>
    get<Campaign[]>(`/campaigns${buildQuery(params)}`),
  createCampaign: (payload: CampaignCreate) => send<Campaign>("POST", "/campaigns", payload),
  setCampaignStatus: (id: number, status: "ACTIVE" | "PAUSED") =>
    send<Campaign>("PATCH", `/campaigns/${id}/status`, { status }),
  updateCampaign: (id: number, payload: CampaignUpdate) =>
    send<Campaign>("PATCH", `/campaigns/${id}`, payload),
  deleteCampaign: (id: number) => send<{ deleted: boolean }>("DELETE", `/campaigns/${id}`),
  templates: (campaignId: number, variant?: string) =>
    get<Template[]>(`/campaigns/${campaignId}/templates${buildQuery({ variant })}`),
  saveTemplateVersion: (campaignId: number, variant: string, body: string) =>
    send<Template>("POST", `/campaigns/${campaignId}/templates`, { variant, body }),

  // Sender accounts
  senderAccounts: () => get<SenderAccount[]>("/sender-accounts"),
  createSenderAccount: (payload: SenderAccountCreate) =>
    send<SenderAccount>("POST", "/sender-accounts", payload),
  updateSenderLimit: (id: number, daily_limit: number) =>
    send<SenderAccount>("PATCH", `/sender-accounts/${id}`, { daily_limit }),

  // Suppression
  suppression: () => get<Suppression[]>("/suppression"),
  addSuppression: (payload: SuppressionCreate) => send<Suppression>("POST", "/suppression", payload),

  // Settings
  settings: () => get<Settings>("/settings"),
  saveSendingWindow: (start_hour: number, end_hour: number) =>
    send<Settings>("PUT", "/settings/sending-window", { start_hour, end_hour }),
  addTargetCity: (city: string, state: string) =>
    send<Settings>("POST", "/settings/target-cities", { city, state }),
  removeTargetCity: (index: number) => send<Settings>("DELETE", `/settings/target-cities/${index}`),
};

/** Default SWR fetcher: the SWR key is the API path. */
export const fetcher = (path: string) => get<unknown>(path);
