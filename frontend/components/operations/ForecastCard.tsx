"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import { useForecast } from "@/lib/hooks";
import { CapacityGauge } from "./CapacityGauge";

export function ForecastCard() {
  const { data, error, isValidating, mutate } = useForecast();
  const loading = !data && !error;

  return (
    <Card
      title="Today’s forecast"
      description="What today’s sending capacity will be spent on, after follow-ups are handled."
      action={
        <Button
          size="sm"
          icon={<RefreshCw className="h-3.5 w-3.5" aria-hidden />}
          loading={isValidating && !!data}
          onClick={() => mutate()}
        >
          Refresh
        </Button>
      }
    >
      {error && !data ? (
        <Notice tone="danger">
          <p className="font-semibold">Couldn’t load the forecast</p>
          <p className="mt-0.5">{error.message}</p>
        </Notice>
      ) : (
        <div className="space-y-5">
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : data ? (
            <CapacityGauge
              sent={data.already_sent_today}
              followupsDue={data.followups_due_today}
              remaining={data.remaining_capacity_today}
              total={data.total_capacity_today}
            />
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label="Emails found today" value={data?.emails_found_today.toLocaleString("en-US")} loading={loading} />
            <Stat label="Ready but not sent yet" value={data?.pending_unsent.toLocaleString("en-US")} loading={loading} />
            <Stat label="Follow-ups due today" value={data?.followups_due_today.toLocaleString("en-US")} loading={loading} />
            <Stat label="Remaining capacity today" value={data?.remaining_capacity_today.toLocaleString("en-US")} loading={loading} />
            <Stat label="Room for new leads" value={data?.room_for_new_leads.toLocaleString("en-US")} loading={loading} />
          </div>

          {data && data.needs_manual_review > 0 && (
            <p className="text-sm text-ink-soft">
              {data.needs_manual_review.toLocaleString("en-US")} researched lead(s) have an email but were held back
              from queuing (invalid, suppressed, or shared with a different business). See{" "}
              <Link href="/leads" className="font-semibold text-accent-dark underline underline-offset-2">
                Manual Review in the Leads tab
              </Link>
              .
            </p>
          )}

          {data &&
            (data.room_for_new_leads <= 0 ? (
              <Notice tone="warn">
                No room left for new leads today. Follow-ups alone will use your full capacity. Skip discovering a new
                city today, or just run replies and follow-ups.
              </Notice>
            ) : data.room_for_new_leads < 10 ? (
              <Notice tone="info">
                Only {data.room_for_new_leads} slot(s) left for new leads today. A small city or a partial batch will fit.
              </Notice>
            ) : (
              <Notice tone="success">
                You have room for up to {data.room_for_new_leads} new leads today after follow-ups are handled.
              </Notice>
            ))}
        </div>
      )}
    </Card>
  );
}
