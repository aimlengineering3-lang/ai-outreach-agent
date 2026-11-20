"use client";

import { FlaskConical, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { useMode } from "@/lib/hooks";
import type { Mode } from "@/lib/types";
import { useAction } from "@/lib/useAction";

export function ModeCard() {
  const { data, mutate } = useMode();
  const [confirming, setConfirming] = useState(false);
  const mode = data?.mode;

  const change = useAction(
    async (next: Mode) => {
      const result = await api.setMode(next);
      // Update the shared cache so the sidebar chip flips at the same moment.
      await mutate(result, { revalidate: false });
      return result;
    },
    { errorTitle: "Couldn’t switch mode" },
  );

  async function apply(next: Mode) {
    const result = await change.run(next);
    if (!result) return;
    setConfirming(false);
    toast.success(
      next === "PRODUCTION"
        ? "Switched to PRODUCTION. Real emails will now be sent."
        : "Switched to TEST. Emails will go to your own inbox only.",
    );
  }

  const production = mode === "PRODUCTION";

  return (
    <Card title="Sending mode" className={production ? "!border-accent-bright/60" : undefined}>
      {!mode ? (
        <Skeleton className="h-10 w-full" />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={
                production
                  ? "grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent-dark"
                  : "grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sunken text-ink-soft"
              }
            >
              {production ? <ShieldAlert className="h-5 w-5" aria-hidden /> : <FlaskConical className="h-5 w-5" aria-hidden />}
            </span>
            <div className="min-w-0">
              <p className="font-semibold">{production ? "Production mode" : "Test mode"}</p>
              <p className="text-sm text-ink-soft">
                {production
                  ? "Emails go to real prospects."
                  : "All emails go to your own inbox, never to real prospects."}
              </p>
            </div>
          </div>

          {production ? (
            <Button onClick={() => apply("TEST")} loading={change.pending}>
              Switch to Test
            </Button>
          ) : (
            <Button variant="primary" onClick={() => setConfirming(true)}>
              Switch to Production
            </Button>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        title="Switch to Production?"
        confirmLabel="Switch to Production"
        loading={change.pending}
        onCancel={() => setConfirming(false)}
        onConfirm={() => apply("PRODUCTION")}
      >
        From now on, every email you send goes to <strong>real prospects</strong>, not your own inbox.
      </ConfirmDialog>
    </Card>
  );
}
