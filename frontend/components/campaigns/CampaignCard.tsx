"use client";

import clsx from "clsx";
import { ChevronDown, Pause, Play, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { api } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import type { Campaign } from "@/lib/types";
import { useAction } from "@/lib/useAction";
import { patchCampaign, removeCampaign, revalidateCampaignViews } from "./campaignCache";
import { FollowupSettings } from "./FollowupSettings";
import { TemplateEditor } from "./TemplateEditor";

export function CampaignCard({ campaign }: { campaign: Campaign }) {
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const active = campaign.status === "ACTIVE";

  const changeStatus = useAction(api.setCampaignStatus, { errorTitle: "Couldn’t change the status" });
  const del = useAction(api.deleteCampaign, { errorTitle: "Couldn’t delete the campaign" });

  async function onToggleStatus() {
    const updated = await changeStatus.run(campaign.id, active ? "PAUSED" : "ACTIVE");
    if (!updated) return;
    patchCampaign(updated);
    revalidateCampaignViews();
  }

  async function onDelete() {
    const result = await del.run(campaign.id);
    if (!result) return;
    setConfirming(false);
    removeCampaign(campaign.id);
    revalidateCampaignViews();
    toast.success(`Deleted “${campaign.name}”`);
  }

  return (
    <section className="rounded-card border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="break-words text-[16px] font-semibold">{campaign.name}</h3>
            <Badge>{titleCase(campaign.niche)}</Badge>
            <StatusBadge status={campaign.status} />
          </div>
          <p className="mt-1 text-[13px] text-ink-mute">
            Created {formatDate(campaign.created_at)} · Follow-up 1 after {campaign.followup1_delay_days} day(s) ·{" "}
            {campaign.followup2_enabled ? `Follow-up 2 after ${campaign.followup2_delay_days} day(s)` : "Follow-up 2 off"}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {active ? (
            <Button
              icon={<Pause className="h-4 w-4" aria-hidden />}
              loading={changeStatus.pending}
              onClick={onToggleStatus}
            >
              Pause
            </Button>
          ) : (
            <Button
              variant="primary"
              icon={<Play className="h-4 w-4" aria-hidden />}
              loading={changeStatus.pending}
              onClick={onToggleStatus}
            >
              Activate
            </Button>
          )}
          <Button
            variant="ghost"
            className="!text-danger hover:!bg-danger-soft"
            icon={<Trash2 className="h-4 w-4" aria-hidden />}
            onClick={() => setConfirming(true)}
          >
            Delete
          </Button>
        </div>
      </div>

      <div className="border-t border-line">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-semibold transition-colors hover:bg-sunken"
        >
          Follow-up timing and templates
          <ChevronDown className={clsx("h-4 w-4 text-ink-mute transition-transform", open && "rotate-180")} aria-hidden />
        </button>
        {open && (
          <div id={panelId} className="space-y-6 border-t border-line px-5 pb-5 pt-4">
            <FollowupSettings campaign={campaign} />
            <div className="border-t border-line pt-5">
              <TemplateEditor campaign={campaign} />
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        danger
        title={`Delete “${campaign.name}”?`}
        confirmLabel="Yes, delete permanently"
        loading={del.pending}
        onCancel={() => setConfirming(false)}
        onConfirm={onDelete}
      >
        This also deletes its templates and email history. This cannot be undone.
      </ConfirmDialog>
    </section>
  );
}
