"use client";

import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export const controlClass =
  "w-full rounded-lg border border-line-strong bg-surface text-sm text-ink placeholder:text-ink-mute/70 " +
  "transition-colors focus:border-accent-bright focus:outline-none focus:ring-2 focus:ring-accent-bright/25 " +
  "disabled:cursor-not-allowed disabled:bg-sunken disabled:text-ink-mute";

interface FieldProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  className?: string;
  /** Receives the generated id so the label is wired to the control. */
  children: (id: string) => ReactNode;
}

export function Field({ label, hint, error, className, children }: FieldProps) {
  const id = useId();
  return (
    <div className={clsx("min-w-0", className)}>
      <label htmlFor={id} className="mb-1.5 block text-[13.5px] font-semibold text-ink">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p className="mt-1.5 text-[13px] text-danger">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-[13px] text-ink-mute">{hint}</p>
      ) : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={clsx(controlClass, "h-10 px-3", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, ...rest },
  ref,
) {
  return <textarea ref={ref} className={clsx(controlClass, "px-3 py-2.5 leading-6", className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { wrapperClassName?: string }>(
  function Select({ className, wrapperClassName, children, ...rest }, ref) {
    return (
      <div className={clsx("relative", wrapperClassName)}>
        <select ref={ref} className={clsx(controlClass, "h-10 appearance-none pl-3 pr-9", className)} {...rest}>
          {children}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-mute" aria-hidden />
      </div>
    );
  },
);

export function Checkbox({
  label,
  className,
  ...rest
}: { label: ReactNode } & Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  return (
    <label className={clsx("inline-flex cursor-pointer items-center gap-2.5 text-sm font-medium text-ink", className)}>
      <input type="checkbox" className="h-4 w-4 rounded border-line-strong accent-[#C8481F]" {...rest} />
      {label}
    </label>
  );
}
