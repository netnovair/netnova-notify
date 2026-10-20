import clsx from "clsx";
import type { ReactNode } from "react";

export type BadgeTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "accent"
  | "mock";

const TONES: Record<BadgeTone, string> = {
  neutral: "border-line bg-white/5 text-muted",
  success: "border-success/30 bg-success/10 text-[#a5efd4]",
  warning: "border-warning/30 bg-warning/10 text-[#f7d478]",
  danger: "border-danger/30 bg-danger/10 text-[#ffb4b4]",
  info: "border-info/30 bg-info/10 text-[#b9d7ff]",
  accent: "border-accent/30 bg-accent/10 text-[#c6b8ff]",
  mock: "border-[#8b5cf6]/40 bg-[#8b5cf6]/10 text-[#d5c8ff]",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className,
}: {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-[10px] font-medium leading-5",
        TONES[tone],
        className,
      )}
    >
      {dot ? <span className="size-1.5 rounded-full bg-current" aria-hidden /> : null}
      {children}
    </span>
  );
}

export function DemoBadge({ label = "نمایشی" }: { label?: string }) {
  return (
    <Badge tone="info" dot>
      {label}
    </Badge>
  );
}
