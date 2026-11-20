"use client";

import { Loader2, Play } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CodeBox } from "@/components/ui/CodeBox";
import { Combobox } from "@/components/ui/Combobox";
import { Field, Select } from "@/components/ui/Field";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { titleCase } from "@/lib/format";
import { useSettings } from "@/lib/hooks";
import { dismissPipeline, formatDuration, startPipeline, useElapsed, useJobs } from "@/lib/jobStore";
import { NICHES } from "@/lib/types";
import { useAction } from "@/lib/useAction";

function Elapsed({ since }: { since: number }) {
  const ms = useElapsed(since);
  return <span className="num">{formatDuration(ms)}</span>;
}

export function PipelineCard() {
  const { data: settings } = useSettings();
  const { pipeline } = useJobs();
  const [niche, setNiche] = useState<string>(NICHES[0]);
  const [cityChoice, setCityChoice] = useState("");
  const start = useAction(startPipeline, { errorTitle: "Couldn’t start the pipeline" });

  const targetCities = settings?.target_cities;
  const options = useMemo(
    () =>
      (targetCities ?? [])
        .map((c) => ({ label: `${c.city}, ${c.state}`, city: c.city, state: c.state }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    [targetCities],
  );
  const selected = options.find((o) => o.label === cityChoice) ?? options[0];
  const running = pipeline.phase === "running";

  async function onRun() {
    if (!selected) return;
    await start.run(niche, selected.city, selected.state);
  }

  return (
    <Card
      title="Run pipeline"
      description="Discovers leads, researches them, and queues eligible ones for the matching campaign. It does not send anything; use “Send all pending now” below to actually send."
    >
      {!settings ? (
        <Skeleton className="h-10 w-full" />
      ) : options.length === 0 ? (
        <Notice tone="info">No target cities yet. Add one in “Target cities” further down this page, then come back here.</Notice>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Niche">
              {(id) => (
                <Select id={id} value={niche} onChange={(e) => setNiche(e.target.value)} disabled={running}>
                  {NICHES.map((n) => (
                    <option key={n} value={n}>
                      {titleCase(n)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="City" hint="Click and type to search. It matches anywhere in the city name.">
              {(id) => (
                <Combobox
                  id={id}
                  options={options.map((o) => o.label)}
                  value={selected?.label ?? ""}
                  onChange={setCityChoice}
                  disabled={running}
                />
              )}
            </Field>
          </div>

          <Button
            variant="primary"
            icon={<Play className="h-4 w-4" aria-hidden />}
            loading={start.pending}
            disabled={running || !selected}
            onClick={onRun}
          >
            {running ? "Pipeline running" : "Run pipeline now"}
          </Button>

          {pipeline.phase === "running" && (
            <Notice tone="info">
              <p className="flex items-center gap-2 font-semibold">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Running discovery, research and queue for {pipeline.label}
              </p>
              <p className="mt-1">
                Elapsed <Elapsed since={pipeline.startedAt} />. This can take a few minutes. You can switch tabs; it keeps
                running as long as the API is up.
              </p>
            </Notice>
          )}

          {pipeline.phase === "done" && (
            <div className="space-y-3">
              <Notice tone="success">
                Finished {pipeline.label} in {formatDuration(pipeline.finishedAt - pipeline.startedAt)}.
              </Notice>
              <CodeBox label="Result">{pipeline.log || "(The pipeline finished without printing anything.)"}</CodeBox>
              <Button size="sm" onClick={dismissPipeline}>
                Clear result
              </Button>
            </div>
          )}

          {pipeline.phase === "error" && (
            <div className="space-y-3">
              <Notice tone="danger">
                <p className="font-semibold">Something interrupted the pipeline for {pipeline.label}</p>
                <p className="mt-1">
                  This is likely a network or database connection issue. Anything already discovered, researched or queued
                  is safely recorded, so it’s safe to just click “Run pipeline now” again.
                </p>
                <p className="mt-1 break-words text-[13px]">Technical detail: {pipeline.message}</p>
              </Notice>
              <Button size="sm" onClick={dismissPipeline}>
                Dismiss
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
