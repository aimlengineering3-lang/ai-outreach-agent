"use client";

/**
 * Long-running jobs (pipeline run, batch send) live here, OUTSIDE React
 * components. That is what lets a job keep going, and its progress keep
 * updating, while you click around to other tabs: leaving Operations only
 * unmounts the card, not the job.
 *
 * - Pipeline: the API runs it in a background thread; we poll every 2s.
 * - Send: the API pushes live events over a WebSocket.
 * - Both remember their job id in sessionStorage, so a full browser reload
 *   re-attaches to a job that is still running on the API.
 *   (If the API itself restarted, the job is gone: we say so plainly.)
 */

import { useEffect, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { mutate } from "swr";
import { ApiError, api, sendProgressUrl } from "./api";
import { titleCase } from "./format";
import type { SendByNicheAssignment, SendEvent, SendSummary } from "./types";

// ---------------------------------------------------------------- types

export type PipelineState =
  | { phase: "idle" }
  | { phase: "running"; jobId: string; label: string; startedAt: number }
  | { phase: "done"; label: string; log: string; startedAt: number; finishedAt: number }
  | { phase: "error"; label: string; message: string; startedAt: number; finishedAt: number };

export type SendConnection = "connecting" | "live" | "lost";

export type SendState =
  | { phase: "idle" }
  | {
      phase: "running";
      jobId: string;
      total: number;
      sent: number;
      campaignName: string | null;
      niche: string | null;
      startedAt: number;
      connection: SendConnection;
      limits: Record<string, number>;
    }
  | {
      phase: "done";
      total: number;
      sent: number;
      summary: SendSummary;
      perNicheSent: Record<string, number>;
      limits: Record<string, number>;
      startedAt: number;
      finishedAt: number;
    }
  | { phase: "error"; message: string; sent: number; total: number; startedAt: number; finishedAt: number };

interface Snapshot {
  pipeline: PipelineState;
  send: SendState;
}

// ---------------------------------------------------------------- store core

const SERVER_SNAPSHOT: Snapshot = { pipeline: { phase: "idle" }, send: { phase: "idle" } };
let snap: Snapshot = SERVER_SNAPSHOT;
const listeners = new Set<() => void>();

function setSnap(partial: Partial<Snapshot>) {
  snap = { ...snap, ...partial };
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useJobs(): Snapshot {
  return useSyncExternalStore(subscribe, () => snap, () => SERVER_SNAPSHOT);
}

/** Refresh everything a finished job may have changed. */
function refreshData() {
  mutate((key) => typeof key === "string" && /^\/(overview|leads|sender-accounts|campaigns)/.test(key));
}

// ---------------------------------------------------------------- session storage

const PIPELINE_KEY = "oa.pipeline";
const SEND_KEY = "oa.send";

function readStored<T>(key: string): T | null {
  try {
    const raw = window.sessionStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
function writeStored(key: string, value: unknown) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage can be blocked; resuming after a reload just won't work */
  }
}
function clearStored(key: string) {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------- pipeline

let pipelineTimer: ReturnType<typeof setInterval> | null = null;

function stopPipelinePolling() {
  if (pipelineTimer) clearInterval(pipelineTimer);
  pipelineTimer = null;
}

function pollPipeline(jobId: string, label: string, startedAt: number) {
  stopPipelinePolling();
  let failures = 0;
  let inFlight = false;

  const fail = (message: string) => {
    stopPipelinePolling();
    clearStored(PIPELINE_KEY);
    setSnap({ pipeline: { phase: "error", label, message, startedAt, finishedAt: Date.now() } });
    toast.error(`Pipeline stopped for ${label}`, { duration: 8000 });
  };

  pipelineTimer = setInterval(async () => {
    if (inFlight) return;
    inFlight = true;
    try {
      const job = await api.pipelineStatus(jobId);
      failures = 0;
      if (job.status === "running") return;

      stopPipelinePolling();
      clearStored(PIPELINE_KEY);
      if (job.status === "done") {
        setSnap({ pipeline: { phase: "done", label, log: job.log ?? "", startedAt, finishedAt: Date.now() } });
        toast.success(`Pipeline finished for ${label}`);
        refreshData();
      } else {
        fail(job.error ?? "Unknown error");
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        fail("The API was restarted, so this run was lost. Anything already saved is safe; just run it again.");
        return;
      }
      failures += 1;
      if (failures >= 5) {
        fail("Lost contact with the API. The pipeline may still be running; check the Overview numbers in a minute.");
      }
    } finally {
      inFlight = false;
    }
  }, 2000);
}

/** Throws on API errors so the calling button can show them. */
export async function startPipeline(niche: string, city: string, state: string): Promise<void> {
  if (snap.pipeline.phase === "running") return;
  const { job_id } = await api.runPipeline(niche, city, state);
  const label = `${titleCase(niche)} in ${city}, ${state}`;
  const startedAt = Date.now();
  setSnap({ pipeline: { phase: "running", jobId: job_id, label, startedAt } });
  writeStored(PIPELINE_KEY, { jobId: job_id, label, startedAt });
  pollPipeline(job_id, label, startedAt);
}

export function dismissPipeline() {
  if (snap.pipeline.phase !== "running") setSnap({ pipeline: { phase: "idle" } });
}

// ---------------------------------------------------------------- send

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempts = 0;

function closeSocket() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (socket) {
    const s = socket;
    socket = null; // so its onclose handler knows this close was on purpose
    s.close();
  }
}

function patchSend(jobId: string, partial: Partial<Extract<SendState, { phase: "running" }>>) {
  const s = snap.send;
  if (s.phase !== "running" || s.jobId !== jobId) return;
  setSnap({ send: { ...s, ...partial } });
}

function failSend(jobId: string, message: string) {
  const s = snap.send;
  if (s.phase !== "running" || s.jobId !== jobId) return;
  closeSocket();
  clearStored(SEND_KEY);
  setSnap({ send: { phase: "error", message, sent: s.sent, total: s.total, startedAt: s.startedAt, finishedAt: Date.now() } });
  toast.error("Sending stopped", { duration: 8000 });
  refreshData();
}

function handleSendEvent(jobId: string, ev: SendEvent) {
  switch (ev.type) {
    case "heartbeat":
      return;
    case "progress":
      patchSend(jobId, { sent: ev.sent, total: ev.total, campaignName: ev.campaign_name, niche: ev.niche ?? null });
      return;
    case "done": {
      const s = snap.send;
      if (s.phase !== "running" || s.jobId !== jobId) return;
      closeSocket();
      clearStored(SEND_KEY);
      setSnap({
        send: {
          phase: "done",
          total: s.total,
          sent: ev.summary.sent,
          summary: ev.summary,
          perNicheSent: ev.per_niche_sent ?? {},
          limits: s.limits,
          startedAt: s.startedAt,
          finishedAt: Date.now(),
        },
      });
      toast.success(`Sent ${ev.summary.sent} email(s)`);
      refreshData();
      return;
    }
    case "error":
      if (ev.message === "Unknown job_id") {
        failSend(jobId, "The API was restarted, so live progress for this send was lost. Open Overview to see today’s sent count.");
      } else {
        failSend(jobId, ev.message);
      }
      return;
  }
}

function connectSend(jobId: string) {
  closeSocket();
  const ws = new WebSocket(sendProgressUrl(jobId));
  socket = ws;

  ws.onopen = () => {
    reconnectAttempts = 0;
    patchSend(jobId, { connection: "live" });
  };
  ws.onmessage = (msg) => {
    let ev: SendEvent;
    try {
      ev = JSON.parse(String(msg.data)) as SendEvent;
    } catch {
      return;
    }
    handleSendEvent(jobId, ev);
  };
  ws.onclose = () => {
    if (socket !== ws) return; // closed on purpose
    socket = null;
    const s = snap.send;
    if (s.phase !== "running" || s.jobId !== jobId) return; // already finished
    // The API keeps the event queue, so reconnecting to the same job just
    // continues where we left off.
    if (reconnectAttempts < 3) {
      reconnectAttempts += 1;
      patchSend(jobId, { connection: "connecting" });
      reconnectTimer = setTimeout(() => connectSend(jobId), 1500);
    } else {
      patchSend(jobId, { connection: "lost" });
    }
  };
  ws.onerror = () => {
    /* onclose always follows and handles the retry */
  };
}

/** Throws on API errors so the calling button can show them. */
export async function startSend(assignments: SendByNicheAssignment[]): Promise<void> {
  if (snap.send.phase === "running") return;
  const { job_id, total_requested } = await api.startSendByNiche(assignments);
  const limits = Object.fromEntries(assignments.map((a) => [a.niche, a.limit]));
  const startedAt = Date.now();
  setSnap({
    send: {
      phase: "running",
      jobId: job_id,
      total: total_requested,
      sent: 0,
      campaignName: null,
      niche: null,
      startedAt,
      connection: "connecting",
      limits,
    },
  });
  writeStored(SEND_KEY, { jobId: job_id, total: total_requested, startedAt, limits });
  reconnectAttempts = 0;
  connectSend(job_id);
}

export function reconnectSend() {
  const s = snap.send;
  if (s.phase !== "running") return;
  reconnectAttempts = 0;
  patchSend(s.jobId, { connection: "connecting" });
  connectSend(s.jobId);
}

export function dismissSend() {
  if (snap.send.phase !== "running") setSnap({ send: { phase: "idle" } });
}

// ---------------------------------------------------------------- resume after reload

let resumed = false;

/** Called once from <Providers>. Safe to call twice (React strict mode). */
export function resumeJobs() {
  if (resumed || typeof window === "undefined") return;
  resumed = true;

  const p = readStored<{ jobId: string; label: string; startedAt: number }>(PIPELINE_KEY);
  if (p && snap.pipeline.phase === "idle") {
    setSnap({ pipeline: { phase: "running", jobId: p.jobId, label: p.label, startedAt: p.startedAt } });
    pollPipeline(p.jobId, p.label, p.startedAt);
  }

  const s = readStored<{ jobId: string; total: number; startedAt: number; limits: Record<string, number> }>(SEND_KEY);
  if (s && snap.send.phase === "idle") {
    setSnap({
      send: {
        phase: "running",
        jobId: s.jobId,
        total: s.total,
        sent: 0,
        campaignName: null,
        niche: null,
        startedAt: s.startedAt,
        connection: "connecting",
        limits: s.limits,
      },
    });
    connectSend(s.jobId);
  }
}

// ---------------------------------------------------------------- small helpers for the UI

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${String(minutes % 60).padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m ${String(totalSeconds % 60).padStart(2, "0")}s`;
  return `${totalSeconds}s`;
}

/** Milliseconds since `startedAt`, ticking once a second. */
export function useElapsed(startedAt: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return startedAt === null ? 0 : Math.max(0, now - startedAt);
}
