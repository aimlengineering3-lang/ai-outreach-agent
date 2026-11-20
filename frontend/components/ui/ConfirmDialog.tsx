"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Button } from "./Button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  /** Shows the spinner on the confirm button while the request runs. */
  loading?: boolean;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Native <dialog>: focus trapping and Esc-to-close come from the browser for free. */
export function ConfirmDialog({
  open, title, children, confirmLabel, loading, danger, onConfirm, onCancel,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        if (!loading) onCancel();
      }}
      className="w-[min(92vw,460px)] rounded-card border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-ink/40"
    >
      <div className="px-6 pb-2 pt-5">
        <h2 className="text-base font-semibold">{title}</h2>
        <div className="mt-2 text-sm text-ink-soft">{children}</div>
      </div>
      <div className="flex justify-end gap-2 px-6 pb-5 pt-4">
        <Button variant="secondary" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
