"use client";

import clsx from "clsx";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/Badge";
import { parseServerDate } from "@/lib/format";
import type { Lead } from "@/lib/types";

export type PixelDisplay = "Found" | "Not Found" | "Unknown";

/** "PRESENT"/"MISSING"/"UNKNOWN"/null meta_pixel -> the label the old dashboard showed. */
export function pixelDisplay(lead: Lead): PixelDisplay {
  if (!lead.meta_pixel || lead.meta_pixel === "UNKNOWN") return "Unknown";
  return lead.meta_pixel === "PRESENT" ? "Found" : "Not Found";
}

function csvDate(value: string | null): string {
  const d = parseServerDate(value);
  if (!d) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function csvEscape(value: unknown): string {
  return `"${String(value ?? "").replace(/"/g, '""')}"`;
}

/**
 * Deliberately more columns than the on-screen table — this is meant to be
 * taken offline (e.g. cold-calling from a phone/printout), same as the old
 * dashboard's download button.
 */
function downloadCsv(leads: Lead[], fileName: string) {
  const header = [
    "Business", "Niche", "City", "State", "Status", "Email", "Email Status",
    "Phone", "Contact Name", "Website", "Meta Pixel", "Google Analytics", "GTM",
    "Created At",
  ];
  const rows = leads.map((l) =>
    [
      l.business_name, l.niche, l.city ?? "", l.state ?? "", l.status,
      l.email ?? "", l.email_status, l.phone ?? "", l.contact_name ?? "",
      l.website ?? "", pixelDisplay(l), l.google_analytics ?? "UNKNOWN", l.gtm ?? "UNKNOWN",
      csvDate(l.created_at),
    ].map(csvEscape),
  );
  const csv = [header.map(csvEscape), ...rows].map((r) => r.join(",")).join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

interface LeadTableProps {
  leads: Lead[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  fileNamePrefix: string;
}

export function LeadTable({ leads, selectedId, onSelect, fileNamePrefix }: LeadTableProps) {
  if (leads.length === 0) {
    return <EmptyState title="No leads match here">Adjust the search or filters above.</EmptyState>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-soft">
          <span className="num font-semibold text-ink">{leads.length}</span> lead{leads.length === 1 ? "" : "s"}
        </p>
        <Button
          size="sm"
          icon={<Download className="h-3.5 w-3.5" aria-hidden />}
          onClick={() => downloadCsv(leads, `leads_${fileNamePrefix}.csv`)}
        >
          Download this list as CSV
        </Button>
      </div>

      <div className="max-h-[28rem] overflow-auto rounded-card border border-line">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="sticky top-0 z-10 bg-sunken text-[13px] text-ink-mute">
            <tr>
              {["Business", "Niche", "City", "State", "Status", "Email", "Phone"].map((h) => (
                <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {leads.map((l) => (
              <tr
                key={l.id}
                onClick={() => onSelect(l.id)}
                aria-selected={selectedId === l.id}
                className={clsx(
                  "cursor-pointer border-t border-line transition-colors hover:bg-sunken",
                  selectedId === l.id && "bg-accent-soft hover:bg-accent-soft",
                )}
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium">{l.business_name}</td>
                <td className="whitespace-nowrap px-3 py-2">{l.niche}</td>
                <td className="whitespace-nowrap px-3 py-2">{l.city ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2">{l.state ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2">
                  <StatusBadge status={l.status} />
                </td>
                <td className="whitespace-nowrap px-3 py-2">{l.email ?? "—"}</td>
                <td className="whitespace-nowrap px-3 py-2">{l.phone ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
