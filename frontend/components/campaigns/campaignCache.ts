import { mutate } from "swr";
import type { Campaign } from "@/lib/types";

// Update the cached campaign list straight from the API response, so the UI
// changes the instant the request finishes (no second round trip to wait for).

export function patchCampaign(updated: Campaign) {
  void mutate<Campaign[]>(
    "/campaigns",
    (current) => current?.map((c) => (c.id === updated.id ? updated : c)),
    { revalidate: false },
  );
}

export function addCampaign(created: Campaign) {
  void mutate<Campaign[]>("/campaigns", (current) => [created, ...(current ?? [])], { revalidate: false });
}

export function removeCampaign(id: number) {
  void mutate<Campaign[]>("/campaigns", (current) => current?.filter((c) => c.id !== id), { revalidate: false });
}

/** Other views of campaigns (e.g. the Send card's list of ACTIVE campaigns) re-fetch quietly. */
export function revalidateCampaignViews() {
  void mutate((key) => typeof key === "string" && key.startsWith("/campaigns?"));
}
