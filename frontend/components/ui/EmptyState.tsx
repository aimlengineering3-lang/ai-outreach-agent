import type { ReactNode } from "react";

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center">
      <p className="text-[15px] font-semibold">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-[52ch] text-sm text-ink-soft">{children}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
