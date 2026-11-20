import clsx from "clsx";
import type { ReactNode } from "react";

export type Tone = "neutral" | "success" | "warn" | "danger" | "accent";

const TONES: Record<Tone, string> = {
  neutral: "bg-[#E8ECF2] text-ink-soft",
  success: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  danger: "bg-danger-soft text-danger",
  accent: "bg-accent-soft text-accent-dark",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold leading-5",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Campaign / sender-account / lead statuses → a consistent colour everywhere. */
export function statusTone(status: string): Tone {
  switch (status) {
    case "ACTIVE":
    case "REPLIED":
    case "valid":
      return "success";
    case "THROTTLED":
    case "NO_REPLY":
      return "warn";
    case "BOUNCED":
    case "SUPPRESSED":
    case "STOPPED":
    case "invalid":
      return "danger";
    case "QUEUED":
    case "CONTACTED":
    case "FOLLOWUP_1":
    case "FOLLOWUP_2":
      return "accent";
    default:
      return "neutral";
  }
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone(status)}>{status}</Badge>;
}
