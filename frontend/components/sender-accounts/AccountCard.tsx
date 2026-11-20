"use client";

import { useState } from "react";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { useAction } from "@/lib/useAction";
import type { SenderAccount } from "@/lib/types";

export function AccountCard({
  account,
  onUpdated,
}: {
  account: SenderAccount;
  onUpdated: (account: SenderAccount) => void;
}) {
  const [limit, setLimit] = useState(String(account.daily_limit));
  const dirty = Number(limit) !== account.daily_limit;

  const update = useAction(api.updateSenderLimit, {
    success: (acc) => `Daily limit updated to ${acc.daily_limit}.`,
    errorTitle: "Couldn't update the limit",
  });

  async function save() {
    const n = Number(limit);
    if (!Number.isFinite(n) || n < 1) return;
    const result = await update.run(account.id, n);
    if (result) onUpdated(result);
  }

  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">
            {account.email} <span className="font-normal text-ink-mute">· {account.provider}</span>
          </p>
        </div>
        <StatusBadge status={account.status} />
      </div>

      <p className="mt-2 text-sm text-ink-soft">
        Available today: <span className="num font-semibold text-ink">{account.available_capacity ?? "—"}</span> /{" "}
        <span className="num">{account.daily_limit}</span>
      </p>
      <p className="mt-1 text-[13px] text-ink-mute">
        Sent today: <span className="num">{account.sent_today}</span> · Bounces (7d):{" "}
        <span className="num">{account.bounce_count_7d}</span> · Complaints (7d):{" "}
        <span className="num">{account.spam_complaint_count_7d}</span>
        {account.capacity_reason ? <> · Reason: {account.capacity_reason}</> : null}
      </p>

      <div className="mt-3.5 flex flex-wrap items-end gap-3 border-t border-line pt-3.5">
        <Field label="Daily email limit" className="w-32">
          {(id) => (
            <Input
              id={id}
              type="number"
              min={1}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
          )}
        </Field>
        <Button variant="secondary" size="sm" loading={update.pending} disabled={!dirty} onClick={save}>
          Update
        </Button>
      </div>
    </div>
  );
}
