"use client";

import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-dark",
  secondary: "border border-line-strong bg-surface text-ink hover:border-ink-mute hover:bg-sunken",
  ghost: "text-ink-soft hover:bg-sunken hover:text-ink",
  danger: "bg-danger text-white hover:bg-[#8F2718]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "md" | "sm";
  /** Shows a spinner on THIS button only and disables it. Nothing else on the page is affected. */
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={clsx(
        "relative inline-flex shrink-0 items-center justify-center rounded-lg font-semibold transition-colors duration-100 disabled:cursor-not-allowed",
        size === "md" ? "h-10 px-4 text-sm" : "h-8 px-3 text-[13px]",
        VARIANTS[variant],
        !loading && "disabled:opacity-50",
        className,
      )}
      {...rest}
    >
      {/* Label stays in layout (just invisible) while loading so the button never changes width. */}
      <span className={clsx("inline-flex items-center gap-2", loading && "invisible")}>
        {icon}
        {children}
      </span>
      {loading && <Loader2 className="absolute h-4 w-4 animate-spin" aria-hidden />}
    </button>
  );
}
