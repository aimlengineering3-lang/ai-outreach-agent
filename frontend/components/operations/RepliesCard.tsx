"use client";

import { Mail } from "lucide-react";
import { useState } from "react";
import { useSWRConfig } from "swr";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CodeBox } from "@/components/ui/CodeBox";
import { api } from "@/lib/api";
import { useAction } from "@/lib/useAction";

export function RepliesCard() {
  const { mutate } = useSWRConfig();
  const [log, setLog] = useState<string | null>(null);

  const check = useAction(api.checkReplies, { errorTitle: "Couldn’t check replies" });

  async function run() {
    const result = await check.run();
    if (!result) return;
    setLog(result.log);
    // Replies/bounces change lead statuses, suppression and the counters.
    mutate("/overview");
    mutate("/overview/forecast");
    mutate("/suppression");
  }

  return (
    <Card
      title="Check for replies"
      description="Checks your inbox for new replies, matches them to leads, and stops follow-ups automatically. Bounces are checked in the same run."
    >
      <div className="flex flex-wrap items-center gap-4">
        <Button
          variant="primary"
          icon={<Mail className="h-4 w-4" aria-hidden />}
          loading={check.pending}
          onClick={run}
        >
          Check replies now
        </Button>
        {check.pending && (
          <p className="text-sm text-ink-soft" role="status">
            Checking every inbox. This can take a minute, and you can keep using the rest of the page.
          </p>
        )}
      </div>

      {log !== null && (
        <div className="mt-4">
          <CodeBox label="Result">{log}</CodeBox>
        </div>
      )}
    </Card>
  );
}
