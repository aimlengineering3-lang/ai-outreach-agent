"use client";

import { Card } from "@/components/ui/Card";
import { Select } from "@/components/ui/Field";
import { StatusBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { useLead } from "@/lib/hooks";
import { formatDateTime } from "@/lib/format";
import type { Lead } from "@/lib/types";

function triDisplay(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "UNKNOWN";
  return value ? "PRESENT" : "MISSING";
}

interface LeadDetailPanelProps {
  /** The currently visible (filtered) rows — used for the fallback "pick a lead" dropdown. */
  leads: Lead[];
  selectedId: number | null;
  onSelectId: (id: number) => void;
}

export function LeadDetailPanel({ leads, selectedId, onSelectId }: LeadDetailPanelProps) {
  if (leads.length === 0) return null;

  const rowIsSelected = selectedId !== null && leads.some((l) => l.id === selectedId);
  const effectiveId = rowIsSelected ? selectedId : leads[0].id;
  const { data: detail, isLoading } = useLead(effectiveId);

  return (
    <Card title="Lead Detail">
      {rowIsSelected ? (
        <p className="mb-4 text-sm text-ink-soft">
          Showing: <span className="font-semibold text-ink">{leads.find((l) => l.id === selectedId)?.business_name}</span>{" "}
          — click another row above to switch.
        </p>
      ) : (
        <Select
          value={effectiveId}
          onChange={(e) => onSelectId(Number(e.target.value))}
          wrapperClassName="mb-4 max-w-sm"
          aria-label="Or pick a lead here"
        >
          {leads.map((l) => (
            <option key={l.id} value={l.id}>
              {l.business_name} (#{l.id})
            </option>
          ))}
        </Select>
      )}

      {isLoading || !detail ? (
        <div className="space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : (
        <div className="rounded-card border border-line p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{detail.business_name}</p>
            <StatusBadge status={detail.status} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 text-sm">
              <p>
                <span className="font-semibold">City/State:</span> {detail.city ?? "—"}, {detail.state ?? "—"}
              </p>
              <p>
                <span className="font-semibold">Website:</span> {detail.website ?? "—"}
              </p>
              <p>
                <span className="font-semibold">Email:</span> {detail.email ?? "—"} ({detail.email_status})
              </p>
              <p>
                <span className="font-semibold">Phone:</span> {detail.phone ?? "—"}
              </p>
              <p>
                <span className="font-semibold">Contact name:</span>{" "}
                {detail.contact_name ?? "Unknown (using fallback greeting)"}
              </p>
            </div>

            <div className="space-y-1.5 text-sm">
              {detail.research ? (
                <>
                  <p>
                    <span className="font-semibold">Meta Pixel:</span> {detail.research.meta_pixel ?? "UNKNOWN"}
                  </p>
                  <p>
                    <span className="font-semibold">Google Analytics:</span> {triDisplay(detail.research.google_analytics)}
                  </p>
                  <p>
                    <span className="font-semibold">GTM:</span> {detail.research.gtm ?? "UNKNOWN"}
                  </p>
                </>
              ) : (
                <p>
                  <span className="font-semibold">Research:</span> Not yet researched.
                </p>
              )}
            </div>
          </div>

          <div className="mt-4 border-t border-line pt-3">
            <p className="mb-1.5 text-sm font-semibold">Outreach history</p>
            {detail.events.length === 0 ? (
              <p className="text-sm text-ink-soft">No outreach history yet.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {detail.events.map((e, i) => (
                  <li key={i} className="text-ink-soft">
                    <code className="rounded bg-sunken px-1.5 py-0.5 text-[12.5px] text-ink">{e.event_type}</code>{" "}
                    — {e.sent_at ? formatDateTime(e.sent_at) : "pending"}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
