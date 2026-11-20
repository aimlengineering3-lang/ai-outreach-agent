"use client";

import { useEffect, type ReactNode } from "react";
import { SWRConfig } from "swr";
import { Toaster } from "sonner";
import { fetcher } from "@/lib/api";
import { resumeJobs } from "@/lib/jobStore";

export function Providers({ children }: { children: ReactNode }) {
  // If a pipeline run or batch send was still going when the page was
  // reloaded, re-attach to it instead of silently losing the progress view.
  useEffect(() => {
    resumeJobs();
  }, []);

  return (
    <SWRConfig
      value={{
        fetcher,
        dedupingInterval: 2000,
        errorRetryCount: 2,
        revalidateOnFocus: true,
        keepPreviousData: true,
      }}
    >
      {children}
      <Toaster position="bottom-right" closeButton toastOptions={{ style: { fontFamily: "var(--font-ui)" } }} />
    </SWRConfig>
  );
}
