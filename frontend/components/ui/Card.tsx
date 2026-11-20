import clsx from "clsx";
import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** Remove inner padding (for tables that should touch the card edges). */
  flush?: boolean;
}

export function Card({ title, description, action, children, className, flush }: CardProps) {
  return (
    <section className={clsx("rounded-card border border-line bg-surface shadow-card", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 pb-0 pt-4">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold leading-6">{title}</h2>}
            {description && <p className="mt-0.5 max-w-[70ch] text-sm text-ink-soft">{description}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={clsx(flush ? "pt-3" : "px-5 pb-5 pt-4", !title && !action && !flush && "pt-5")}>{children}</div>
    </section>
  );
}
