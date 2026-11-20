"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Input } from "@/components/ui/Field";
import { api } from "@/lib/api";
import type { Campaign } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { patchCampaign, revalidateCampaignViews } from "./campaignCache";

export function FollowupSettings({ campaign }: { campaign: Campaign }) {
  // null = "show the saved value"; typing turns it into a draft.
  const [draft1, setDraft1] = useState<string | null>(null);
  const [draft2, setDraft2] = useState<string | null>(null);

  const toggle = useAction(api.updateCampaign, { errorTitle: "Couldn’t update follow-up 2" });
  const saveDelays = useAction(api.updateCampaign, { success: "Follow-up delays updated.", errorTitle: "Couldn’t update the delays" });

  const text1 = draft1 ?? String(campaign.followup1_delay_days);
  const text2 = draft2 ?? String(campaign.followup2_delay_days);
  const d1 = Number(text1);
  const d2 = Number(text2);
  const err1 = !Number.isInteger(d1) || d1 < 1 ? "Whole days, 1 or more." : null;
  const err2 = !Number.isInteger(d2) || d2 < 1 ? "Whole days, 1 or more." : null;
  const dirty = d1 !== campaign.followup1_delay_days || d2 !== campaign.followup2_delay_days;

  async function onToggle(checked: boolean) {
    const updated = await toggle.run(campaign.id, { followup2_enabled: checked });
    if (!updated) return;
    patchCampaign(updated);
    revalidateCampaignViews();
  }

  async function onSaveDelays() {
    const updated = await saveDelays.run(campaign.id, { followup1_delay_days: d1, followup2_delay_days: d2 });
    if (!updated) return;
    patchCampaign(updated);
    revalidateCampaignViews();
    setDraft1(null);
    setDraft2(null);
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-soft">
        Follow-up 1: <strong className="num text-ink">{campaign.followup1_delay_days}</strong> day(s) after the initial send ·
        Follow-up 2: <strong className="num text-ink">{campaign.followup2_delay_days}</strong> day(s) after follow-up 1
        {!campaign.followup2_enabled && " (follow-up 2 is off)"}
      </p>

      <Checkbox
        label="Send follow-up 2"
        checked={campaign.followup2_enabled}
        disabled={toggle.pending}
        onChange={(e) => onToggle(e.target.checked)}
      />

      <div className="flex flex-wrap items-start gap-4">
        <Field label="Follow-up 1 delay (days)" error={err1} className="w-48">
          {(id) => (
            <Input id={id} type="number" inputMode="numeric" min={1} value={text1} onChange={(e) => setDraft1(e.target.value)} />
          )}
        </Field>
        <Field label="Follow-up 2 delay (days)" error={err2} className="w-48">
          {(id) => (
            <Input id={id} type="number" inputMode="numeric" min={1} value={text2} onChange={(e) => setDraft2(e.target.value)} />
          )}
        </Field>
        <div className="pt-[27px]">
          <Button
            variant="primary"
            loading={saveDelays.pending}
            disabled={!dirty || !!err1 || !!err2}
            onClick={onSaveDelays}
          >
            Update delays
          </Button>
        </div>
      </div>
    </div>
  );
}
