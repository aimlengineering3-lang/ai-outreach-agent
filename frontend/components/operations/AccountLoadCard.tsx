"use client";

import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { useSenderAccounts } from "@/lib/hooks";

export function AccountLoadCard() {
  const { data, error } = useSenderAccounts();

  return (
    <Card title="Sender accounts today" description="How many emails each account has sent today, against its daily limit.">
      {error && !data ? (
        <Notice tone="danger">{error.message}</Notice>
      ) : !data ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : data.length === 0 ? (
        <p className="text-sm text-ink-soft">
          No sender accounts configured yet. Add one in{" "}
          <Link href="/sender-accounts" className="font-semibold text-accent-dark underline underline-offset-2">
            Sender Accounts
          </Link>
          .
        </p>
      ) : (
        <ul className="-my-3 divide-y divide-line">
          {data.map((a) => {
            const pct = a.daily_limit > 0 ? Math.min(100, (a.sent_today / a.daily_limit) * 100) : 0;
            return (
              <li
                key={a.id}
                className="grid items-center gap-x-5 gap-y-2 py-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto]"
              >
                <div className="min-w-0">
                  <p className="truncate font-semibold">{a.email}</p>
                  <p className="text-[13px] capitalize text-ink-mute">{a.provider}</p>
                </div>
                <div>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="num">
                      <strong>{a.sent_today}</strong> sent today
                    </span>
                    <span className="num text-ink-mute">limit {a.daily_limit}/day</span>
                  </div>
                  <span aria-hidden className="mt-1.5 block h-1.5 rounded-full bg-sunken">
                    <span className="block h-1.5 rounded-full bg-accent-bright" style={{ width: `${pct}%` }} />
                  </span>
                </div>
                <StatusBadge status={a.status} />
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
