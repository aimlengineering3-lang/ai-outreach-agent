"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { useAction } from "@/lib/useAction";
import type { SenderAccount } from "@/lib/types";

const PROVIDERS = ["gmail", "outlook", "proton"] as const;

const EMPTY_FORM = { email: "", provider: PROVIDERS[0] as string, daily_limit: "50" };

export function AddSenderAccountCard({ onAdded }: { onAdded: (account: SenderAccount) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const create = useAction(api.createSenderAccount, {
    success: (acc) => `Added ${acc.email}.`,
  });

  async function submit() {
    if (!form.email.trim()) {
      setError("Email is required.");
      return;
    }
    const limit = Number(form.daily_limit);
    if (!Number.isFinite(limit) || limit < 1) {
      setError("Daily limit must be at least 1.");
      return;
    }
    setError(null);
    const result = await create.run({ email: form.email.trim(), provider: form.provider, daily_limit: limit });
    if (result) {
      onAdded(result);
      setForm(EMPTY_FORM);
      setOpen(false);
    }
  }

  return (
    <Card title="Add Sender Account" flush>
      <div className="px-5 pb-5">
        {!open ? (
          <Button variant="secondary" onClick={() => setOpen(true)}>
            + Add account
          </Button>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Email address" error={error}>
                {(id) => (
                  <Input
                    id={id}
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Provider">
                {(id) => (
                  <Select id={id} value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
                    {PROVIDERS.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Daily limit">
                {(id) => (
                  <Input
                    id={id}
                    type="number"
                    min={1}
                    value={form.daily_limit}
                    onChange={(e) => setForm({ ...form, daily_limit: e.target.value })}
                  />
                )}
              </Field>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <Button variant="primary" loading={create.pending} onClick={submit}>
                Add Account
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setOpen(false);
                  setForm(EMPTY_FORM);
                  setError(null);
                }}
              >
                Cancel
              </Button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
