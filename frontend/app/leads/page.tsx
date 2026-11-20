"use client";

import clsx from "clsx";
import { useState } from "react";
import { AddLeadCard } from "@/components/leads/AddLeadCard";
import { LeadDetailPanel } from "@/components/leads/LeadDetailPanel";
import { LeadTable, pixelDisplay } from "@/components/leads/LeadTable";
import { PageHeader } from "@/components/shell/PageHeader";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { useLeadFilterOptions, useLeads } from "@/lib/hooks";

const PIXEL_OPTIONS = ["All", "Found", "Not Found", "Unknown"] as const;
type PixelOption = (typeof PIXEL_OPTIONS)[number];

// Mirrors the old dashboard's cap — a single unbounded query was taking 5.4s.
const LEADS_PAGE_LIMIT = 500;

const TABS = [
  ["has_email", "Has Email (auto-outreach)"],
  ["manual", "Manual Review (no email found)"],
] as const;
type TabKey = (typeof TABS)[number][0];

export default function LeadsPage() {
  const [search, setSearch] = useState("");
  const [niche, setNiche] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pixel, setPixel] = useState<PixelOption>("All");
  const [tab, setTab] = useState<TabKey>("has_email");
  const [selectedHasEmail, setSelectedHasEmail] = useState<number | null>(null);
  const [selectedManual, setSelectedManual] = useState<number | null>(null);

  const { data: filterOptions } = useLeadFilterOptions();
  const {
    data: leads,
    error,
  } = useLeads({
    search: search || undefined,
    niche: niche || undefined,
    city: city || undefined,
    state: state || undefined,
  });

  const pixelFiltered = (leads ?? []).filter((l) => pixel === "All" || pixelDisplay(l) === pixel);
  const hasEmailResults = pixelFiltered.filter((l) => l.email);
  const manualResults = pixelFiltered.filter((l) => !l.email);
  const activeResults = tab === "has_email" ? hasEmailResults : manualResults;
  const selectedId = tab === "has_email" ? selectedHasEmail : selectedManual;
  const setSelectedId = tab === "has_email" ? setSelectedHasEmail : setSelectedManual;

  return (
    <>
      <PageHeader
        title="Leads"
        description="Search and filter leads, add one manually, open a lead's full research and outreach history, and export a list to take offline."
      />

      <div className="space-y-6">
        <AddLeadCard />

        <Card title="Search Leads">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Search" className="sm:col-span-2 lg:col-span-4">
              {(id) => (
                <Input
                  id={id}
                  placeholder="Search by business name, email, or website…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              )}
            </Field>
            <Field label="Filter by niche">
              {(id) => (
                <Select id={id} value={niche} onChange={(e) => setNiche(e.target.value)}>
                  <option value="">All niches</option>
                  {filterOptions?.niches.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Filter by city">
              {(id) => (
                <Select id={id} value={city} onChange={(e) => setCity(e.target.value)}>
                  <option value="">All cities</option>
                  {filterOptions?.cities.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Filter by state">
              {(id) => (
                <Select id={id} value={state} onChange={(e) => setState(e.target.value)}>
                  <option value="">All states</option>
                  {filterOptions?.states.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Filter by pixel">
              {(id) => (
                <Select id={id} value={pixel} onChange={(e) => setPixel(e.target.value as PixelOption)}>
                  {PIXEL_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </Card>

        {leads && leads.length === LEADS_PAGE_LIMIT && (
          <Notice tone="info">
            Showing the {LEADS_PAGE_LIMIT} most recent matching leads. Use search/filters above to narrow it down further.
          </Notice>
        )}

        <div>
          <div className="mb-4 flex gap-1 border-b border-line" role="tablist">
            {TABS.map(([key, label]) => (
              <button
                key={key}
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                className={clsx(
                  "-mb-px rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors",
                  tab === key ? "border-accent text-accent-dark" : "border-transparent text-ink-mute hover:text-ink",
                )}
              >
                {label}{" "}
                <span className="num font-normal">
                  ({key === "has_email" ? hasEmailResults.length : manualResults.length})
                </span>
              </button>
            ))}
          </div>

          {error && !leads ? (
            <Notice tone="danger">
              <p className="font-semibold">Couldn't load leads</p>
              <p className="mt-0.5">{error.message}</p>
            </Notice>
          ) : !leads ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : (
            <div className="space-y-6">
              <LeadTable leads={activeResults} selectedId={selectedId} onSelect={setSelectedId} fileNamePrefix={tab} />
              <LeadDetailPanel leads={activeResults} selectedId={selectedId} onSelectId={setSelectedId} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
