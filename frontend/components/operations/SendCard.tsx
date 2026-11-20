"use client";

import clsx from "clsx";
import { Loader2, Send } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { titleCase } from "@/lib/format";
import { useCampaigns, useForecast, useMode, useNicheStats } from "@/lib/hooks";
import {
  dismissSend,
  formatDuration,
  reconnectSend,
  startSend,
  useElapsed,
  useJobs,
  type SendState,
} from "@/lib/jobStore";
import type { SendSummary } from "@/lib/types";
import { useAction } from "@/lib/useAction";

// ------------------------------------------------------------ live progress

function SendProgress({ send }: { send: Extract<SendState, { phase: "running" }> }) {
  const elapsed = useElapsed(send.startedAt);
  const pct = send.total > 0 ? Math.min(100, (send.sent / send.total) * 100) : 0;

  return (
    <div className="rounded-lg border border-line-strong bg-sunken p-4" role="status" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">Sent so far</p>
        <p className="text-[13px] text-ink-mute">
          Elapsed <span className="num">{formatDuration(elapsed)}</span>
        </p>
      </div>
      <p className="num mt-1 text-[32px] font-semibold leading-10 tracking-tight">
        {send.sent} <span className="text-ink-mute">/ {send.total}</span>
      </p>
      <span aria-hidden className="mt-2 block h-2.5 rounded-full bg-line">
        <span className="block h-2.5 rounded-full bg-accent-bright transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </span>

      <p className="mt-3 text-sm text-ink-soft">
        {send.campaignName ? (
          <>
            Working on <strong>{send.campaignName}</strong>
            {send.niche ? ` (${titleCase(send.niche)})` : ""}
          </>
        ) : (
          "Waiting for the first email to go out"
        )}
      </p>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-ink-mute">
        {send.connection === "live" && (
          <span className="flex items-center gap-1.5">
            <span aria-hidden className="h-2 w-2 rounded-full bg-ok" /> Live
          </span>
        )}
        {send.connection === "connecting" && (
          <span className="flex items-center gap-1.5">
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Connecting to live progress
          </span>
        )}
        {send.connection === "lost" && (
          <>
            <span className="text-warn">
              Lost the live connection. The send may still be running in the background.
            </span>
            <Button size="sm" onClick={reconnectSend}>
              Reconnect
            </Button>
          </>
        )}
        <span>Emails go out one at a time with a pause between them. You can switch tabs.</span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------ final result

function skippedDetails(s: SendSummary): string[] {
  const out: string[] = [];
  if (s.skipped_no_capacity > 0) out.push(`${s.skipped_no_capacity} email(s) skipped: sender account capacity used up for today.`);
  if (s.skipped_outside_window > 0)
    out.push(`${s.skipped_outside_window} email(s) held back: outside the prospect’s business hours right now.`);
  if (s.skipped_no_template > 0)
    out.push(`${s.skipped_no_template} email(s) skipped: no template found. Add one in the Campaigns tab.`);
  if (s.skipped_suppressed > 0) out.push(`${s.skipped_suppressed} email(s) skipped: on the do-not-contact list.`);
  return out;
}

function SendResult({ send }: { send: Exclude<SendState, { phase: "idle" } | { phase: "running" }> }) {
  if (send.phase === "error") {
    return (
      <div className="space-y-3">
        <Notice tone="danger">
          <p className="font-semibold">Something went wrong while sending</p>
          <p className="mt-1">
            Likely a network or database problem. Any emails already sent are safely recorded, so it’s safe to just send
            again.
          </p>
          <p className="mt-1 break-words text-[13px]">Technical detail: {send.message}</p>
        </Notice>
        <Button size="sm" onClick={dismissSend}>
          Dismiss
        </Button>
      </div>
    );
  }

  const details = skippedDetails(send.summary);
  const perNiche = Object.entries(send.perNicheSent);
  return (
    <div className="space-y-3">
      <Notice tone={send.summary.sent > 0 ? "success" : "warn"}>
        <p className="font-semibold">
          {send.summary.sent > 0 ? `Sent ${send.summary.sent} email(s) in total.` : "No emails were sent."}{" "}
          <span className="font-normal">Took {formatDuration(send.finishedAt - send.startedAt)}.</span>
        </p>
        {perNiche.length > 0 && (
          <ul className="mt-1.5 list-disc space-y-0.5 pl-5">
            {perNiche.map(([niche, n]) => (
              <li key={niche}>
                {titleCase(niche)}: sent {n} (your limit was {send.limits[niche] ?? "unknown"})
              </li>
            ))}
          </ul>
        )}
      </Notice>
      {details.length > 0 && (
        <div className="rounded-lg border border-line px-4 py-3 text-sm">
          <p className="font-semibold">Details</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-soft">
            {details.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      )}
      <Button size="sm" onClick={dismissSend}>
        Clear result
      </Button>
    </div>
  );
}

// ------------------------------------------------------------ the card

export function SendCard() {
  const forecast = useForecast();
  const nicheStats = useNicheStats();
  const campaignsQuery = useCampaigns({ status: "ACTIVE" });
  const mode = useMode();
  const { send } = useJobs();

  const [pickedNiches, setPickedNiches] = useState<string[] | null>(null); // null = all
  const [pickedCampaigns, setPickedCampaigns] = useState<number[]>([]); // default: none, on purpose
  const [limits, setLimits] = useState<Record<string, string>>({});
  const [confirming, setConfirming] = useState(false);

  const starter = useAction(startSend, { errorTitle: "Couldn’t start sending" });

  const activeCampaigns = campaignsQuery.data;
  const nichesAvailable = useMemo(
    () => Array.from(new Set((activeCampaigns ?? []).map((c) => c.niche))).sort(),
    [activeCampaigns],
  );

  const nichesSelected = (pickedNiches ?? nichesAvailable).filter((n) => nichesAvailable.includes(n));
  const campaignsForNiches = (activeCampaigns ?? []).filter((c) => nichesSelected.includes(c.niche));
  // Same order as the campaign list: a niche's budget is spent campaign by campaign in this order.
  const campaignsSelected = campaignsForNiches.filter((c) => pickedCampaigns.includes(c.id));
  const nichesInCampaigns = Array.from(new Set(campaignsSelected.map((c) => c.niche))).sort();

  const remaining = forecast.data?.remaining_capacity_today ?? 0;
  const parseLimit = (niche: string) => {
    const n = Number.parseInt(limits[niche] ?? "0", 10);
    return Number.isFinite(n) && n > 0 ? n : 0;
  };
  const limitFor = Object.fromEntries(nichesInCampaigns.map((n) => [n, parseLimit(n)])) as Record<string, number>;
  const totalRequested = Object.values(limitFor).reduce((a, b) => a + b, 0);
  const overCapacity = totalRequested > remaining;

  const running = send.phase === "running";
  const loadingData = !forecast.data || !activeCampaigns;
  const canSend = !loadingData && !running && totalRequested > 0 && !overCapacity;
  const production = mode.data?.mode === "PRODUCTION";

  const assignments = nichesInCampaigns
    .filter((n) => limitFor[n] > 0)
    .map((n) => ({
      niche: n,
      limit: limitFor[n],
      campaign_ids: campaignsSelected.filter((c) => c.niche === n).map((c) => c.id),
    }));

  function toggleNiche(niche: string) {
    const base = pickedNiches ?? nichesAvailable;
    setPickedNiches(base.includes(niche) ? base.filter((n) => n !== niche) : [...base, niche]);
  }
  function toggleCampaign(id: number) {
    setPickedCampaigns((cur) => (cur.includes(id) ? cur.filter((c) => c !== id) : [...cur, id]));
  }

  async function doSend() {
    await starter.run(assignments);
    setConfirming(false);
  }
  function onSendClick() {
    if (production) setConfirming(true);
    else void doSend();
  }

  const stats = [...(nicheStats.data ?? [])].sort((a, b) => a.niche.localeCompare(b.niche));

  return (
    <Card
      title="Send all pending now"
      description="Pick niches and campaigns, set how many emails to send per niche, then send. The limit shown is your sender accounts’ real remaining capacity today, not a fixed number."
    >
      <div className="space-y-5">
        {send.phase === "running" && <SendProgress send={send} />}
        {(send.phase === "done" || send.phase === "error") && <SendResult send={send} />}

        {loadingData ? (
          <div className="space-y-3">
            <Skeleton className="h-5 w-72" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : (
          <fieldset disabled={running} className="m-0 min-w-0 space-y-5 border-0 p-0">
            <p className="text-sm text-ink-soft">
              Sent today: <strong className="num text-ink">{forecast.data?.already_sent_today}</strong> · Remaining capacity
              today: <strong className="num text-ink">{remaining}</strong> /{" "}
              <span className="num">{forecast.data?.total_capacity_today}</span>
            </p>

            {stats.length > 0 && (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="bg-sunken text-left text-[13px] text-ink-soft">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Niche</th>
                      <th className="px-3 py-2 text-right font-semibold">New leads pending</th>
                      <th className="px-3 py-2 text-right font-semibold">Follow-ups pending</th>
                      <th className="px-3 py-2 text-right font-semibold">Sent today</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {stats.map((s) => (
                      <tr key={s.niche}>
                        <td className="px-3 py-2 font-medium">{titleCase(s.niche)}</td>
                        <td className="num px-3 py-2 text-right">{s.new_pending}</td>
                        <td className="num px-3 py-2 text-right">{s.followup_pending}</td>
                        <td className="num px-3 py-2 text-right">{s.sent_today}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {(activeCampaigns ?? []).length === 0 ? (
              <Notice tone="info">
                There are no active campaigns to send from. Create or activate one in the{" "}
                <Link href="/campaigns" className="font-semibold underline underline-offset-2">
                  Campaigns
                </Link>{" "}
                tab.
              </Notice>
            ) : (
              <>
                <div className="border-t border-line pt-5">
                  <p className="mb-2 text-[13.5px] font-semibold">Niches</p>
                  <div className="flex flex-wrap gap-2">
                    {nichesAvailable.map((n) => {
                      const on = nichesSelected.includes(n);
                      return (
                        <button
                          key={n}
                          type="button"
                          aria-pressed={on}
                          onClick={() => toggleNiche(n)}
                          className={clsx(
                            "h-9 rounded-full border px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                            on
                              ? "border-ink bg-ink text-white"
                              : "border-line-strong bg-surface text-ink-soft hover:border-ink-mute hover:text-ink",
                          )}
                        >
                          {titleCase(n)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-[13.5px] font-semibold">Campaigns (pick one or more)</p>
                  {campaignsForNiches.length === 0 ? (
                    <p className="text-sm text-ink-soft">Select at least one niche above to see its campaigns.</p>
                  ) : (
                    <div className="space-y-3">
                      {nichesSelected.map((n) => {
                        const rows = campaignsForNiches.filter((c) => c.niche === n);
                        if (rows.length === 0) return null;
                        return (
                          <fieldset key={n} className="m-0 rounded-lg border border-line px-4 pb-3 pt-2">
                            <legend className="px-1 text-[13px] font-semibold text-ink-soft">{titleCase(n)}</legend>
                            <div className="flex flex-col gap-2">
                              {rows.map((c) => (
                                <Checkbox
                                  key={c.id}
                                  label={`${c.name} (#${c.id})`}
                                  checked={pickedCampaigns.includes(c.id)}
                                  onChange={() => toggleCampaign(c.id)}
                                />
                              ))}
                            </div>
                          </fieldset>
                        );
                      })}
                    </div>
                  )}
                  <p className="mt-2 text-[13px] text-ink-mute">
                    Nothing is selected by default, so you never send by accident. When a niche has several campaigns, its
                    limit is spent on them in the order listed.
                  </p>
                </div>

                {nichesInCampaigns.length > 0 && (
                  <div>
                    <p className="mb-2 text-[13.5px] font-semibold">How many emails per niche</p>
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                      {nichesInCampaigns.map((n) => {
                        const stat = stats.find((s) => s.niche === n);
                        const own = limitFor[n];
                        return (
                          <Field
                            key={n}
                            label={titleCase(n)}
                            error={own > remaining ? `More than today’s remaining capacity (${remaining}).` : null}
                            hint={stat ? `${stat.new_pending} new · ${stat.followup_pending} follow-ups pending` : undefined}
                          >
                            {(id) => (
                              <Input
                                id={id}
                                type="number"
                                inputMode="numeric"
                                min={0}
                                max={Math.max(remaining, 0)}
                                step={10}
                                value={limits[n] ?? "0"}
                                onChange={(e) => setLimits((cur) => ({ ...cur, [n]: e.target.value }))}
                              />
                            )}
                          </Field>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="space-y-3 border-t border-line pt-5">
                  <p className="text-sm text-ink-soft">
                    Total selected: <strong className="num text-ink">{totalRequested}</strong> · Remaining capacity today:{" "}
                    <strong className="num text-ink">{remaining}</strong>
                  </p>
                  {overCapacity && (
                    <Notice tone="danger">
                      Total ({totalRequested}) is more than today’s remaining capacity ({remaining}). Lower the numbers above.
                    </Notice>
                  )}
                  {mode.data && (
                    <Notice tone={production ? "warn" : "info"}>
                      {production
                        ? "Production mode is on. These emails go to real prospects."
                        : "Test mode is on. These emails go to your own inbox, not to prospects."}
                    </Notice>
                  )}
                  <Button
                    variant="primary"
                    icon={<Send className="h-4 w-4" aria-hidden />}
                    loading={starter.pending}
                    disabled={!canSend}
                    onClick={onSendClick}
                  >
                    Send all pending emails
                  </Button>
                </div>
              </>
            )}
          </fieldset>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        title={`Send ${totalRequested} email(s) to real prospects?`}
        confirmLabel="Send now"
        loading={starter.pending}
        onCancel={() => setConfirming(false)}
        onConfirm={doSend}
      >
        <p>Production mode is on, so these go to real businesses and can’t be recalled.</p>
        <ul className="mt-2 list-disc space-y-0.5 pl-5">
          {assignments.map((a) => (
            <li key={a.niche}>
              {titleCase(a.niche)}: up to {a.limit}
            </li>
          ))}
        </ul>
      </ConfirmDialog>
    </Card>
  );
}
