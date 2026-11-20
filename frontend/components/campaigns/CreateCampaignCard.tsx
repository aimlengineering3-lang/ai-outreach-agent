"use client";

import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { NICHES } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { addCampaign, revalidateCampaignViews } from "./campaignCache";

interface Errors {
  name?: string;
  f1?: string;
  f2?: string;
}

export function CreateCampaignCard() {
  const [name, setName] = useState("");
  const [niche, setNiche] = useState<string>(NICHES[0]);
  const [f1, setF1] = useState("1");
  const [f2, setF2] = useState("1");
  const [f2On, setF2On] = useState(true);
  const [errors, setErrors] = useState<Errors>({});

  const create = useAction(api.createCampaign, { errorTitle: "Couldn’t create the campaign" });

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    const d1 = Number(f1);
    const d2 = Number(f2);

    const next: Errors = {};
    if (!trimmed) next.name = "Campaign name is required.";
    if (!Number.isInteger(d1) || d1 < 1) next.f1 = "Enter a whole number of days, 1 or more.";
    if (!Number.isInteger(d2) || d2 < 1) next.f2 = "Enter a whole number of days, 1 or more.";
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const created = await create.run({
      name: trimmed,
      niche,
      followup1_delay_days: d1,
      followup2_delay_days: d2,
      followup2_enabled: f2On,
    });
    if (!created) return;

    addCampaign(created);
    revalidateCampaignViews();
    toast.success(`Campaign “${trimmed}” created. It starts paused, so activate it below when you’re ready.`);
    setName("");
    setF1("1");
    setF2("1");
    setF2On(true);
  }

  return (
    <Card title="Create a campaign" description="New campaigns start paused, so nothing is sent until you activate them.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Campaign name" error={errors.name}>
            {(id) => (
              <Input
                id={id}
                placeholder="e.g. Plumbing – Texas Q1"
                value={name}
                onChange={(e) => setName(e.target.value)}
                aria-invalid={!!errors.name}
              />
            )}
          </Field>
          <Field label="Niche">
            {(id) => (
              <Select id={id} value={niche} onChange={(e) => setNiche(e.target.value)}>
                {NICHES.map((n) => (
                  <option key={n} value={n}>
                    {titleCase(n)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Follow-up 1 delay (days)" error={errors.f1}>
            {(id) => (
              <Input id={id} type="number" inputMode="numeric" min={1} value={f1} onChange={(e) => setF1(e.target.value)} />
            )}
          </Field>
          <Field label="Follow-up 2 delay (days)" error={errors.f2}>
            {(id) => (
              <Input id={id} type="number" inputMode="numeric" min={1} value={f2} onChange={(e) => setF2(e.target.value)} />
            )}
          </Field>
        </div>
        <Checkbox label="Send follow-up 2" checked={f2On} onChange={(e) => setF2On(e.target.checked)} />
        <div>
          <Button type="submit" variant="primary" icon={<Plus className="h-4 w-4" aria-hidden />} loading={create.pending}>
            Create campaign
          </Button>
        </div>
      </form>
    </Card>
  );
}
