"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { NICHES } from "@/lib/types";
import { useAction } from "@/lib/useAction";

const EMPTY_FORM = { business_name: "", niche: NICHES[0] as string, city: "", state: "", website: "", email: "" };

export function AddLeadCard() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const { mutate } = useSWRConfig();

  const create = useAction(api.createLead, {
    success: (lead) => `Added '${lead.business_name}'.`,
  });

  async function submit() {
    if (!form.business_name.trim()) {
      setError("Business name is required.");
      return;
    }
    setError(null);
    const result = await create.run({
      business_name: form.business_name.trim(),
      niche: form.niche,
      city: form.city.trim() || null,
      state: form.state.trim() || null,
      website: form.website.trim() || null,
      email: form.email.trim() || null,
    });
    if (result) {
      setForm(EMPTY_FORM);
      setOpen(false);
      // Revalidate every /leads* key (list + filter-options) so the new lead shows up right away.
      mutate((key) => typeof key === "string" && key.startsWith("/leads"));
    }
  }

  return (
    <Card title="Add a Lead Manually" flush>
      <div className="px-5 pb-5">
        {!open ? (
          <Button variant="secondary" onClick={() => setOpen(true)}>
            + Add lead
          </Button>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Business name" error={error}>
                {(id) => (
                  <Input
                    id={id}
                    value={form.business_name}
                    onChange={(e) => setForm({ ...form, business_name: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Niche">
                {(id) => (
                  <Select id={id} value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value })}>
                    {NICHES.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="City">
                {(id) => <Input id={id} value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />}
              </Field>
              <Field label="State (2-letter)">
                {(id) => (
                  <Input
                    id={id}
                    maxLength={2}
                    value={form.state}
                    onChange={(e) => setForm({ ...form, state: e.target.value.toUpperCase() })}
                  />
                )}
              </Field>
              <Field label="Website">
                {(id) => (
                  <Input id={id} value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
                )}
              </Field>
              <Field label="Email">
                {(id) => (
                  <Input
                    id={id}
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                )}
              </Field>
            </div>
            <div className="mt-4 flex items-center gap-2">
              <Button variant="primary" loading={create.pending} onClick={submit}>
                Add Lead
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
