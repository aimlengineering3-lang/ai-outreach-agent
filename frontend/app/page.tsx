"use client";

import clsx from "clsx";
import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/shell/PageHeader";
import { statusTone, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import { titleCase } from "@/lib/format";
import { useOverview } from "@/lib/hooks";

// Order a lead moves through the pipeline (src/core/state_machine.py),
// followed by the end states. The old dashboard sorted these alphabetically,
// which hid the shape of the funnel.
const STAGE_ORDER = [
  "NEW", "RESEARCHED", "QUEUED", "CONTACTED", "FOLLOWUP_1", "FOLLOWUP_2",
  "REPLIED", "NO_REPLY", "COMPLETED", "STOPPED", "BOUNCED", "SUPPRESSED",
];

const BAR_COLOR: Record<Tone, string> = {
  neutral: "bg-ink-mute",
  accent: "bg-accent-bright",
  success: "bg-ok",
  warn: "bg-warn",
  danger: "bg-danger",
};

function orderedStatuses(counts: Record<string, number>) {
  const known = STAGE_ORDER.filter((s) => (counts[s] ?? 0) > 0);
  const extra = Object.keys(counts)
    .filter((s) => !STAGE_ORDER.includes(s) && counts[s] > 0)
    .sort();
  return [...known, ...extra];
}

function StatusFunnel({ counts, total }: { counts: Record<string, number>; total: number }) {
  const statuses = orderedStatuses(counts);
  const max = Math.max(...statuses.map((s) => counts[s]), 1);

  return (
    <ul className="space-y-2.5">
      {statuses.map((status) => {
        const n = counts[status];
        const width = Math.max(1.5, (n / max) * 100);
        const pct = total > 0 ? (n / total) * 100 : 0;
        return (
          <li key={status} className="grid grid-cols-[7.5rem_1fr_4.5rem_3.5rem] items-center gap-3 text-sm">
            <span className="truncate font-medium">{titleCase(status)}</span>
            <span aria-hidden className="h-3 rounded-full bg-sunken">
              <span
                className={clsx("block h-3 rounded-full", BAR_COLOR[statusTone(status)])}
                style={{ width: `${width}%` }}
              />
            </span>
            <span className="num text-right font-semibold">{n.toLocaleString("en-US")}</span>
            <span className="num text-right text-ink-mute">{pct < 1 ? "<1" : Math.round(pct)}%</span>
          </li>
        );
      })}
    </ul>
  );
}

function SentTodayHint({ sent, capacity }: { sent: number; capacity: number }) {
  const pct = capacity > 0 ? Math.min(100, (sent / capacity) * 100) : 0;
  return (
    <span className="mt-2 block">
      <span aria-hidden className="block h-1.5 rounded-full bg-sunken">
        <span className="block h-1.5 rounded-full bg-accent-bright" style={{ width: `${pct}%` }} />
      </span>
      <span className="mt-1.5 block">
        {capacity > 0 ? `${Math.round(pct)}% of today's capacity` : "No active sender accounts"}
      </span>
    </span>
  );
}

export default function OverviewPage() {
  const { data, error, isValidating, mutate } = useOverview();
  const loading = !data && !error;

  const researchedPct =
    data && data.total_leads > 0 ? Math.round((data.researched / data.total_leads) * 100) : null;
  const replyCategories = data ? Object.entries(data.reply_categories) : [];

  return (
    <>
      <PageHeader
        title="Overview"
        description="Where your outreach stands right now. Numbers refresh on their own every 30 seconds."
        actions={
          <Button
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
            loading={isValidating && !!data}
            onClick={() => mutate()}
          >
            Refresh
          </Button>
        }
      />

      {error && !data ? (
        <Notice tone="danger">
          <p className="font-semibold">Couldn&apos;t load the overview</p>
          <p className="mt-0.5">{error.message}</p>
          <div className="mt-3">
            <Button size="sm" onClick={() => mutate()}>
              Try again
            </Button>
          </div>
        </Notice>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label="Leads discovered" value={data?.total_leads.toLocaleString("en-US")} loading={loading} />
            <Stat
              label="Researched"
              value={data?.researched.toLocaleString("en-US")}
              hint={researchedPct !== null ? `${researchedPct}% of all leads` : undefined}
              loading={loading}
            />
            <Stat
              label="Emails sent today"
              value={data ? `${data.sent_today} / ${data.total_daily_capacity}` : undefined}
              hint={data ? <SentTodayHint sent={data.sent_today} capacity={data.total_daily_capacity} /> : undefined}
              loading={loading}
            />
            <Stat label="Replies" value={data?.replies.toLocaleString("en-US")} loading={loading} />
            <Stat label="Suppressed" value={data?.suppressed.toLocaleString("en-US")} loading={loading} />
          </div>

          <Card
            title="Leads by status"
            description="Every lead sits at one stage. Stages run in the order a lead moves through them."
          >
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            ) : data && data.total_leads > 0 ? (
              <StatusFunnel counts={data.status_counts} total={data.total_leads} />
            ) : (
              <EmptyState title="No leads yet">
                Add one in the{" "}
                <Link href="/leads" className="font-semibold text-accent-dark underline underline-offset-2">
                  Leads
                </Link>{" "}
                tab, or run the pipeline from{" "}
                <Link href="/operations" className="font-semibold text-accent-dark underline underline-offset-2">
                  Operations
                </Link>{" "}
                to fill this in automatically.
              </EmptyState>
            )}
          </Card>

          {replyCategories.length > 0 && (
            <Card title="Replies by category" description="How the replies so far were classified.">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {replyCategories.map(([category, count]) => (
                  <Stat key={category} label={titleCase(category)} value={count.toLocaleString("en-US")} />
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  );
}