import clsx from "clsx";
import type { ReactNode } from "react";
import { Skeleton } from "./Skeleton";

interface StatProps {
  label: string;
  value?: ReactNode;
  hint?: ReactNode;
  /** True while the first load is in flight — shows a placeholder instead of a wrong 0. */
  loading?: boolean;
  className?: string;
}

export function Stat({ label, value, hint, loading, className }: StatProps) {
  return (
    <div className={clsx("rounded-card border border-line bg-surface px-4 py-3.5 shadow-card", className)}>
      <p className="text-[13px] font-medium text-ink-soft">{label}</p>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className="num mt-1 text-[28px] font-semibold leading-9 tracking-tight">{value}</p>
      )}
      {hint && !loading && <p className="mt-0.5 text-[13px] text-ink-mute">{hint}</p>}
    </div>
  );
}
