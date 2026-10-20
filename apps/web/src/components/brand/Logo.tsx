import clsx from "clsx";

export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <span
      aria-hidden
      className="relative inline-flex items-center justify-center rounded-xl bg-accent/15 ring-1 ring-inset ring-accent/30"
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 24 24"
        width={size * 0.62}
        height={size * 0.62}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-[#bfaeff]"
      >
        <path d="M6 9a6 6 0 0 1 12 0c0 3.4 1 4.7 1.6 5.3H4.4C5 13.7 6 12.4 6 9Z" />
        <path d="M9.8 18a2.4 2.4 0 0 0 4.4 0" />
      </svg>
      <span className="absolute end-1 top-1 size-1.5 rounded-full bg-success" />
    </span>
  );
}

export function Logo({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  return (
    <span className={clsx("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={compact ? 32 : 38} />
      {compact ? null : (
        <span className="leading-tight">
          <span className="block text-sm font-semibold text-ink">NetNova Notify</span>
          <span className="block text-[11px] text-muted">مرکز اطلاع رسانی نت نووا</span>
        </span>
      )}
    </span>
  );
}
