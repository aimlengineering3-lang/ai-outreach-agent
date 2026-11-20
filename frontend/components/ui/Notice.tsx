import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";

type NoticeTone = "info" | "success" | "warn" | "danger";

const STYLES: Record<NoticeTone, { box: string; icon: ReactNode }> = {
  info: { box: "border-[#C9D6EC] bg-[#EEF3FB] text-[#1F3A66]", icon: <Info className="h-4 w-4" /> },
  success: { box: "border-[#BFE0CC] bg-ok-soft text-ok", icon: <CheckCircle2 className="h-4 w-4" /> },
  warn: { box: "border-[#F0D9A0] bg-warn-soft text-warn", icon: <AlertTriangle className="h-4 w-4" /> },
  danger: { box: "border-[#F0C4BC] bg-danger-soft text-danger", icon: <XCircle className="h-4 w-4" /> },
};

export function Notice({ tone = "info", children, className }: { tone?: NoticeTone; children: ReactNode; className?: string }) {
  const s = STYLES[tone];
  return (
    <div
      role={tone === "danger" || tone === "warn" ? "alert" : "status"}
      className={clsx("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm", s.box, className)}
    >
      <span className="mt-0.5 shrink-0">{s.icon}</span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
