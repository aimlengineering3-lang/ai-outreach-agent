"use client";

import { AccountCard } from "@/components/sender-accounts/AccountCard";
import { AddSenderAccountCard } from "@/components/sender-accounts/AddSenderAccountCard";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Notice } from "@/components/ui/Notice";
import { Skeleton } from "@/components/ui/Skeleton";
import { useSenderAccounts } from "@/lib/hooks";

export default function SenderAccountsPage() {
  const { data, error, mutate } = useSenderAccounts();

  return (
    <>
      <PageHeader
        title="Sender Accounts"
        description="Add the mailboxes you send from and see their health, capacity, and today's usage."
      />

      <div className="space-y-6">
        <AddSenderAccountCard onAdded={() => mutate()} />

        <section aria-labelledby="accounts">
          <h2 id="accounts" className="mb-3 text-[18px] font-semibold">
            Accounts {data && <span className="num font-normal text-ink-mute">({data.length})</span>}
          </h2>

          {error && !data ? (
            <Notice tone="danger">
              <p className="font-semibold">Couldn't load sender accounts</p>
              <p className="mt-0.5">{error.message}</p>
              <div className="mt-3">
                <Button size="sm" onClick={() => mutate()}>
                  Try again
                </Button>
              </div>
            </Notice>
          ) : !data ? (
            <div className="space-y-3">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : data.length === 0 ? (
            <EmptyState title="No sender accounts yet">Add your first one above.</EmptyState>
          ) : (
            <div className="space-y-3">
              {data.map((account) => (
                <AccountCard
                  key={account.id}
                  account={account}
                  onUpdated={(updated) =>
                    mutate(
                      (current) => current?.map((a) => (a.id === updated.id ? updated : a)),
                      { revalidate: false },
                    )
                  }
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
