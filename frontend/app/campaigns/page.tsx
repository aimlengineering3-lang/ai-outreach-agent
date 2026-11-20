"use client";

import { CampaignCard } from "@/components/campaigns/CampaignCard";
import { CreateCampaignCard } from "@/components/campaigns/CreateCampaignCard";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCampaigns } from "@/lib/hooks";

export default function CampaignsPage() {
  const { data, error, mutate } = useCampaigns();

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Create campaigns, set follow-up timing, and edit the email templates each one sends. Templates are never edited in place: saving always creates a new version."
      />

      <div className="space-y-8">
        <CreateCampaignCard />

        <section aria-labelledby="your-campaigns">
          <h2 id="your-campaigns" className="mb-3 text-[18px] font-semibold">
            Your campaigns {data && <span className="num font-normal text-ink-mute">({data.length})</span>}
          </h2>

          {error && !data ? (
            <Notice tone="danger">
              <p className="font-semibold">Couldn’t load your campaigns</p>
              <p className="mt-0.5">{error.message}</p>
              <div className="mt-3">
                <Button size="sm" onClick={() => mutate()}>
                  Try again
                </Button>
              </div>
            </Notice>
          ) : !data ? (
            <div className="space-y-3">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : data.length === 0 ? (
            <EmptyState title="No campaigns yet">Create your first one above.</EmptyState>
          ) : (
            <div className="space-y-3">
              {data.map((campaign) => (
                <CampaignCard key={campaign.id} campaign={campaign} />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
