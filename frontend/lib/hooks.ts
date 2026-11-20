"use client";

import useSWR, { type SWRConfiguration } from "swr";
import { buildQuery } from "./api";
import type {
  Campaign, ForecastStats, Lead, LeadDetail, LeadFilterOptions, Mode, NicheStat,
  OverviewStats, SenderAccount, Settings, Suppression, Template,
} from "./types";

// Every key IS the API path, and the global fetcher (see Providers.tsx)
// just calls it. SWR shows cached data instantly on navigation and
// refreshes in the background — that's what makes tab switches feel instant.

export const useHealth = () =>
  useSWR<{ status: string }>("/health", {
    refreshInterval: 15_000,
    shouldRetryOnError: false,
    revalidateOnFocus: true,
  });

export const useMode = () => useSWR<{ mode: Mode }>("/operations/mode");

export const useOverview = (config?: SWRConfiguration) =>
  useSWR<OverviewStats>("/overview", { refreshInterval: 30_000, ...config });

export const useForecast = (config?: SWRConfiguration) =>
  useSWR<ForecastStats>("/overview/forecast", { refreshInterval: 30_000, ...config });

export const useNicheStats = () => useSWR<NicheStat[]>("/leads/niche-stats");

export const useCampaigns = (params: { niche?: string; status?: string } = {}) =>
  useSWR<Campaign[]>(`/campaigns${buildQuery(params)}`);

export const useTemplates = (campaignId: number | null, variant?: string) =>
  useSWR<Template[]>(
    campaignId === null ? null : `/campaigns/${campaignId}/templates${buildQuery({ variant })}`,
  );

export const useSenderAccounts = () => useSWR<SenderAccount[]>("/sender-accounts");

export const useSuppression = () => useSWR<Suppression[]>("/suppression");

export const useSettings = () => useSWR<Settings>("/settings");

export const useLeadFilterOptions = () => useSWR<LeadFilterOptions>("/leads/filter-options");

export const useLeads = (params: {
  search?: string; niche?: string; city?: string; state?: string; has_email?: boolean;
}) => useSWR<Lead[]>(`/leads${buildQuery(params)}`, { keepPreviousData: true });

export const useLead = (id: number | null) => useSWR<LeadDetail>(id === null ? null : `/leads/${id}`);