"use client";

import { AddSuppressionCard } from "@/components/suppression/AddSuppressionCard";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatDate } from "@/lib/format";
import { useSuppression } from "@/lib/hooks";

export default function SuppressionPage() {
  const { data, error, mutate } = useSuppression();

  return (
    <>
      <PageHeader
        title="Suppression List"
        description="Addresses that are never emailed again — unsubscribes, hard bounces, or anything added manually."
      />

      <div className="space-y-6">
        <AddSuppressionCard onAdded={() => mutate()} />

        <Card
          title="Suppressed Contacts"
          description={data ? `${data.length} ${data.length === 1 ? "contact" : "contacts"}` : undefined}
        >
          {error && !data ? (
            <Notice tone="danger">
              <p className="font-semibold">Couldn't load the suppression list</p>
              <p className="mt-0.5">{error.message}</p>
              <div className="mt-3">
                <Button size="sm" onClick={() => mutate()}>
                  Try again
                </Button>
              </div>
            </Notice>
          ) : !data ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          ) : data.length === 0 ? (
            <EmptyState title="No suppressed contacts yet">Add one above.</EmptyState>
          ) : (
            <div className="max-h-[28rem] overflow-auto rounded-card border border-line">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="sticky top-0 z-10 bg-sunken text-[13px] text-ink-mute">
                  <tr>
                    {["Email", "Reason", "Permanent", "Added"].map((h) => (
                      <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.map((r) => (
                    <tr key={r.id} className="border-t border-line">
                      <td className="whitespace-nowrap px-3 py-2 font-medium">{r.email}</td>
                      <td className="whitespace-nowrap px-3 py-2">{r.reason}</td>
                      <td className="whitespace-nowrap px-3 py-2">{r.permanent ? "Yes" : "No (90-day cooldown)"}</td>
                      <td className="whitespace-nowrap px-3 py-2">{formatDate(r.added_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
