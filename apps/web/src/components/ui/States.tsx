"use client";

import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/Button";

export function LoadingState({
  label = "در حال بارگذاری...",
  compact = false,
}: {
  label?: string;
  compact?: boolean;
}) {
  return (
    <div
      role="status"
      className={`flex flex-col items-center justify-center gap-3 ${compact ? "py-8" : "py-14"}`}
    >
      <span className="size-7 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  compact = false,
}: {
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center gap-3 px-4 text-center ${compact ? "py-8" : "py-12"}`}
    >
      <span className="flex size-11 items-center justify-center rounded-2xl border border-danger/30 bg-danger/10 text-danger">
        <AlertCircle size={20} aria-hidden />
      </span>
      <p className="max-w-sm text-xs leading-7 text-muted">{message}</p>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw size={13} aria-hidden />
          تلاش دوباره
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center">
      <span className="flex size-11 items-center justify-center rounded-2xl border border-line bg-elevated text-muted">
        {icon ?? <Inbox size={20} aria-hidden />}
      </span>
      <p className="text-sm font-medium text-ink">{title}</p>
      {description ? (
        <p className="max-w-md text-[11px] leading-7 text-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

export function InlineAlert({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  children: ReactNode;
}) {
  const tones = {
    info: "border-info/30 bg-info/[0.07] text-[#b9d7ff]",
    warning: "border-warning/30 bg-warning/[0.07] text-[#f7d478]",
    danger: "border-danger/30 bg-danger/[0.07] text-[#ffb4b4]",
    success: "border-success/30 bg-success/[0.07] text-[#a5efd4]",
  } as const;
  return (
    <div role="status" className={`rounded-xl border px-3.5 py-2.5 text-[11px] leading-6 ${tones[tone]}`}>
      {children}
    </div>
  );
}

export function SkeletonRows({ rows = 5 }: { rows?: number }) {
  return (
    <div
      role="status"
      aria-label="در حال بارگذاری"
      className="space-y-3 p-4"
    >
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="flex items-center gap-4">
          <div className="skeleton h-4 w-1/3" />
          <div className="skeleton h-4 w-1/4" />
          <div className="skeleton h-4 w-1/5" />
          <div className="skeleton ms-auto h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function StatSkeleton() {
  return (
    <div className="panel p-5">
      <div className="skeleton mb-4 h-3 w-24" />
      <div className="skeleton h-8 w-16" />
    </div>
  );
}
