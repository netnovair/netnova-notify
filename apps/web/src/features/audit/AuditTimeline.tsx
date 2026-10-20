"use client";

import { Activity } from "lucide-react";

import { EmptyState } from "@/components/ui/States";
import { formatDateTime, formatRelative } from "@/lib/format";
import type { AuditLog } from "@/types/api";

const CONTEXT_LABELS: Record<string, string> = {
  error: "خطا",
  reason: "دلیل",
  prefix: "پیشوند لایسنس",
  members_revoked: "کاربران قطع شده",
  changed: "تغییرات",
  amount_minor: "مبلغ",
  currency: "واحد پول",
  due_at: "سررسید",
  recipients: "گیرندگان",
  attempt: "تلاش",
  telegram_message_id: "شناسه پیام",
  project: "پروژه",
  name: "نام",
  slug: "شناسه",
  type: "نوع",
  features: "قابلیت ها",
  job_id: "شناسه کار",
  scheduled_at: "زمان بندی",
  telegram_id: "شناسه تلگرام",
  previous_status: "وضعیت قبلی",
  previous_attempts: "تلاش های قبلی",
  run_at: "زمان اجرا",
  notification_id: "شناسه اطلاعیه",
  ip: "آی پی",
  email: "ایمیل",
};

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(renderValue).join("، ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${CONTEXT_LABELS[key] ?? key}: ${renderValue(item)}`)
      .join(" · ");
  }
  return String(value);
}

export function AuditTimeline({ logs }: { logs: AuditLog[] }) {
  if (logs.length === 0) {
    return (
      <EmptyState
        icon={<Activity size={22} aria-hidden />}
        title="فعالیتی ثبت نشده است"
        description="عملیات مهم مانند ایجاد پروژه، صدور لایسنس، ارسال اطلاعیه و تغییر وضعیت پرداخت در این بخش ثبت می شود."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {logs.map((log) => {
        const entries = Object.entries(log.context ?? {})
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .slice(0, 4);
        return (
          <li key={log.id} className="panel-muted p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="size-1.5 rounded-full bg-accent" aria-hidden />
                <p className="text-sm font-medium text-ink">
                  {log.action_label ?? log.action}
                </p>
              </div>
              <time
                dateTime={log.created_at}
                title={formatDateTime(log.created_at)}
                className="text-[11px] text-muted"
              >
                {formatRelative(log.created_at)}
              </time>
            </div>
            <p className="mt-1 text-[11px] text-muted">
              {log.actor_label ?? log.actor_type} · {formatDateTime(log.created_at)}
            </p>
            {entries.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {entries.map(([key, value]) => (
                  <span
                    key={key}
                    className="max-w-full truncate rounded-md bg-elevated px-2 py-0.5 text-[10px] text-muted"
                  >
                    {CONTEXT_LABELS[key] ?? key}: {renderValue(value)}
                  </span>
                ))}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
