"use client";

import clsx from "clsx";
import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "subtle";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-white shadow-lg shadow-accent/20 hover:bg-accent-strong disabled:shadow-none",
  secondary:
    "border border-line bg-elevated text-ink hover:border-accent/50 hover:bg-[#182442]",
  ghost: "text-muted hover:bg-white/5 hover:text-ink",
  danger: "bg-danger/15 text-[#ffb4b4] border border-danger/30 hover:bg-danger/25",
  subtle: "bg-white/5 text-ink hover:bg-white/10",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 rounded-lg px-2.5 text-[11px] gap-1.5",
  md: "h-10 rounded-xl px-4 text-xs gap-2",
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  block = false,
  className,
  disabled,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  block?: boolean;
  children?: ReactNode;
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={clsx(
        "inline-flex select-none items-center justify-center font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTS[variant],
        SIZES[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
}
