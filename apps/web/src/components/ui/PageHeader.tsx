import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  subtitle,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  /** Alias kept for the page-level copy used across the panel. */
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  const body = description ?? subtitle;
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-[10px] font-medium tracking-wide text-accent">{eyebrow}</p>
        ) : null}
        <h1 className="truncate text-xl font-semibold sm:text-2xl">{title}</h1>
        {body ? (
          <p className="mt-1 text-[11px] leading-6 text-muted sm:text-xs">{body}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
