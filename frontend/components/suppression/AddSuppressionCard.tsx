"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { useAction } from "@/lib/useAction";
import type { Suppression } from "@/lib/types";

const REASONS = ["unsubscribe", "manual", "bounce_hard"] as const;

const EMPTY_FORM = { email: "", reason: REASONS[0] as string, permanent: true };

export function AddSuppressionCard({ onAdded }: { onAdded: (record: Suppression) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const create = useAction(api.addSuppression, {
    success: (record) => `Suppressed ${record.email}.`,
  });

  async function submit() {
    if (!form.email.trim()) {
      setError("Email is required.");
      return;
    }
    setError(null);
    const result = await create.run({ email: form.email.trim(), reason: form.reason, permanent: form.permanent });
    if (result) {
      onAdded(result);
      setForm(EMPTY_FORM);
      setOpen(false);
    }
  }

  return (
    <Card title="Add Suppression" flush>
      <div className="px-5 pb-5">
        {!open ? (
          <Button variant="secondary" onClick={() => setOpen(true)}>
            + Add manually
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
              <Field label="Reason">
                {(id) => (
                  <Select id={id} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}>
                    {REASONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <div className="flex items-end pb-2.5">
                <Checkbox
                  label="Permanent"
                  checked={form.permanent}
                  onChange={(e) => setForm({ ...form, permanent: e.target.checked })}
                />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <Button variant="primary" loading={create.pending} onClick={submit}>
                Add
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
