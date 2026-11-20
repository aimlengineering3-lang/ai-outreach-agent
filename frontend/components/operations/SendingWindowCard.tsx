"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { useSettings } from "@/lib/hooks";
import { useAction } from "@/lib/useAction";

export function SendingWindowCard() {
  const { data, mutate } = useSettings();
  // null = "show the saved value". Once the user types, the draft takes over.
  const [draftStart, setDraftStart] = useState<string | null>(null);
  const [draftEnd, setDraftEnd] = useState<string | null>(null);

  const save = useAction(api.saveSendingWindow, { success: "Sending window updated", errorTitle: "Couldn’t save" });

  if (!data) {
    return (
      <Card title="Sending window">
        <Skeleton className="h-10 w-full" />
      </Card>
    );
  }

  const savedStart = data.sending_window.start_hour;
  const savedEnd = data.sending_window.end_hour;
  const startText = draftStart ?? String(savedStart);
  const endText = draftEnd ?? String(savedEnd);
  const start = Number(startText);
  const end = Number(endText);

  let startError: string | null = null;
  let endError: string | null = null;
  if (startText.trim() === "" || !Number.isInteger(start) || start < 0 || start > 23) startError = "Enter a whole hour from 0 to 23.";
  if (endText.trim() === "" || !Number.isInteger(end) || end < 1 || end > 24) endError = "Enter a whole hour from 1 to 24.";
  if (!startError && !endError && end <= start) endError = "End hour must be after the start hour.";

  const dirty = start !== savedStart || end !== savedEnd;

  async function onSave() {
    const result = await save.run(start, end);
    if (!result) return;
    await mutate(result, { revalidate: false });
    setDraftStart(null);
    setDraftEnd(null);
  }

  return (
    <Card
      title="Sending window"
      description="Emails only send inside this local-time window, measured in each prospect’s own US timezone."
    >
      <div className="flex flex-wrap items-start gap-4">
        <Field label="Start hour (24h)" error={startError} className="w-40">
          {(id) => (
            <Input
              id={id}
              type="number"
              inputMode="numeric"
              min={0}
              max={23}
              value={startText}
              onChange={(e) => setDraftStart(e.target.value)}
              aria-invalid={!!startError}
            />
          )}
        </Field>
        <Field label="End hour (24h)" error={endError} className="w-40">
          {(id) => (
            <Input
              id={id}
              type="number"
              inputMode="numeric"
              min={1}
              max={24}
              value={endText}
              onChange={(e) => setDraftEnd(e.target.value)}
              aria-invalid={!!endError}
            />
          )}
        </Field>
        {/* 27px = label height + gap, so the button lines up with the inputs */}
        <div className="pt-[27px]">
          <Button
            variant="primary"
            loading={save.pending}
            disabled={!dirty || !!startError || !!endError}
            onClick={onSave}
          >
            Save sending window
          </Button>
        </div>
      </div>
    </Card>
  );
}
