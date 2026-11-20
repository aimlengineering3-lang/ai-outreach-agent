"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "./Button";

/** Dark, scrollable box for logs (pipeline output, reply-check output). */
export function CodeBox({ children, label = "Output" }: { children: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard can be blocked; nothing useful to do */
    }
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line-strong bg-ink">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="text-xs font-medium text-rail-mute">{label}</span>
        <Button
          variant="ghost"
          size="sm"
          className="!text-rail-text hover:!bg-white/10 hover:!text-white"
          icon={copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
          onClick={copy}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words px-4 py-3 font-mono text-[13px] leading-5 text-[#DCE3F0]">
        {children}
      </pre>
    </div>
  );
}
