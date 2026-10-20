"use client";

import {
  AlertTriangle,
  ArrowLeft,
  BellRing,
  CalendarClock,
  FolderKanban,
  KeyRound,
  RefreshCw,
  Send,
  Settings,
  ShieldAlert,
  UserCheck,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/Badge";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, InlineAlert, LoadingState } from "@/components/ui/States";
import { api, errorMessage } from "@/lib/api";
import { formatAmount, formatDateTime, formatNumber, formatRelative } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { Currency, Dashboard, SystemStatus } from "@/types/api";

const CURRENCY_ORDER: Currency[] = ["IRT", "IRR", "USD", "EUR"];

function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
  href,
}: {
  label: string;
  value: string;
  hint?: React.ReactNode;
  icon: React.ReactNode;
  tone?: "default" | "warning" | "danger";
  href?: string;
}) {
  const content = (
    <div className="panel h-full p-4 transition hover:border-accent/30 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-muted">{label}</span>
        <span
          className={
            tone === "danger"
              ? "text-danger/80"
              : tone === "warning"
                ? "text-warning/80"
                : "text-[#b9a7ff]"
          }
        >
          {icon}
        </span>
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {hint ? <div className="mt-1.5 text-[10px] leading-6 text-muted">{hint}</div> : null}
    </div>
  );
  return href ? (
    <Link href={href} className="block rounded-2xl">
      {content}
    </Link>
  ) : (
    content
  );
}

export default function DashboardPage() {
  const { admin } = useAuth();
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const dashboard = useApiData<Dashboard>((signal) => api.get("/dashboard", signal));
  const status = useApiData<SystemStatus>((signal) => api.get("/system/status", signal));

  async function reloadAll() {
    dashboard.reload();
    status.reload();
    setRefreshedAt(new Date());
  }

  const data = dashboard.data;
  const system = status.data;
  const paymentTotals = CURRENCY_ORDER.filter(
    (currency) => (data?.open_payments_amount_by_currency?.[currency] ?? 0) > 0,
  );

  return (
    <>
      <PageHeader
        eyebrow="نمای کلی"
        title={`سلام، ${admin?.display_name ?? "مدیر"}`}
        subtitle={
          data
            ? `آخرین به روزرسانی: ${formatRelative(data.generated_at)} · همه اعداد از داده واقعی پایگاه داده خوانده می شوند.`
            : "در حال دریافت وضعیت..."
        }
        actions={
          <button
            type="button"
            onClick={() => void reloadAll()}
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-line bg-elevated px-3 text-xs text-ink transition hover:border-accent/50"
          >
            <RefreshCw
              size={14}
              aria-hidden
              className={dashboard.refreshing ? "animate-spin" : ""}
            />
            به روزرسانی
          </button>
        }
      />

      {system ? (
        <div className="mb-5 space-y-2">
          {system.telegram.mode === "mock" ? (
            <InlineAlert tone="info">
              ربات در حالت شبیه سازی است؛ پیام ها واقعی ارسال نمی شوند و در جدول ارسال
              با نشان «Mock» مشخص می شوند.
            </InlineAlert>
          ) : null}
          {system.worker.status !== "online" ? (
            <InlineAlert tone="warning">
              Worker در حال اجرا نیست یا گزارش تازه ای ندارد. اطلاعیه های در صف و یادآوری
              پرداخت ها تا اجرای Worker ارسال نمی شوند.
            </InlineAlert>
          ) : null}
          {system.failed_jobs > 0 ? (
            <InlineAlert tone="danger">
              {formatNumber(system.failed_jobs)} کار پس زمینه با خطای نهایی ثبت شده است.
              جزئیات در تنظیمات و لاگ سرور قابل بررسی است.
            </InlineAlert>
          ) : null}
        </div>
      ) : null}

      {dashboard.error && !data ? (
        <div className="panel">
          <ErrorState message={dashboard.error} onRetry={dashboard.reload} />
        </div>
      ) : dashboard.loading && !data ? (
        <LoadingState label="در حال دریافت آمار..." />
      ) : !data ? null : data.projects_total === 0 ? (
        <div className="panel">
          <div className="px-6 py-12 text-center">
            <span className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl border border-line bg-elevated text-[#b9a7ff]">
              <FolderKanban size={24} aria-hidden />
            </span>
            <h2 className="text-base font-semibold">هنوز پروژه ای ثبت نشده است</h2>
            <p className="mx-auto mt-2 max-w-md text-xs leading-7 text-muted">
              با ایجاد اولین پروژه، لایسنس اختصاصی آن صادر می شود و می توانید اطلاعیه و
              پرداخت ثبت کنید. اعداد این صفحه تا آن زمان صفر است.
            </p>
            <Link
              href="/projects"
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-xl bg-accent px-4 text-sm font-medium text-white transition hover:bg-accent-strong"
            >
              <FolderKanban size={16} aria-hidden />
              رفتن به پروژه ها
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            <StatCard
              label="پروژه های فعال"
              value={`${formatNumber(data.projects_active)} از ${formatNumber(data.projects_total)}`}
              hint="پروژه های غیرفعال عملیات کارفرما را متوقف می کنند."
              icon={<FolderKanban size={17} aria-hidden />}
              href="/projects"
            />
            <StatCard
              label="اطلاعیه های در صف"
              value={formatNumber(data.queued_notifications)}
              hint={`از مجموع ${formatNumber(data.notifications_total)} اطلاعیه ثبت شده`}
              icon={<Send size={17} aria-hidden />}
              href="/notifications?status=queued"
            />
            <StatCard
              label="پرداخت های باز"
              value={formatNumber(data.open_payments)}
              hint={
                paymentTotals.length
                  ? paymentTotals
                      .map(
                        (currency) =>
                          `${formatAmount(
                            data.open_payments_amount_by_currency[currency] ?? 0,
                            currency,
                          )}`,
                      )
                      .join(" · ")
                  : "مبلغ بازی وجود ندارد"
              }
              icon={<Wallet size={17} aria-hidden />}
              href="/payments?status=unpaid"
            />
            <StatCard
              label="ارسال های ناموفق"
              value={formatNumber(data.failed_notifications)}
              hint={
                data.failed_notifications > 0
                  ? "نیازمند بررسی خطا و تلاش مجدد"
                  : "ارسال ناموفقی ثبت نشده است"
              }
              tone={data.failed_notifications > 0 ? "danger" : "default"}
              icon={<AlertTriangle size={17} aria-hidden />}
              href="/notifications?status=failed"
            />
            <StatCard
              label="در انتظار تایید اتصال"
              value={formatNumber(data.pending_members)}
              hint={
                data.pending_members > 0
                  ? "درخواست کارفرما در انتظار تایید شماست"
                  : "درخواست تایید نشده ای وجود ندارد"
              }
              tone={data.pending_members > 0 ? "warning" : "default"}
              icon={<UserCheck size={17} aria-hidden />}
              href="/projects"
            />
            <StatCard
              label="لایسنس های نزدیک انقضا"
              value={formatNumber(data.license_attention)}
              hint={
                data.license_attention > 0
                  ? "کمتر از ۱۴ روز اعتبار دارند"
                  : "لایسنس نیازمند تمدید نیست"
              }
              tone={data.license_attention > 0 ? "warning" : "default"}
              icon={<ShieldAlert size={17} aria-hidden />}
              href="/licenses"
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <section className="panel p-5 lg:col-span-2" aria-labelledby="recent-activity-title">
              <div className="mb-3 flex items-center justify-between">
                <h2 id="recent-activity-title" className="text-sm font-semibold">
                  فعالیت های اخیر
                </h2>
                <span className="text-[10px] text-muted">ثبت شده در Audit</span>
              </div>
              {data.recent_activity.length === 0 ? (
                <p className="rounded-xl border border-line-soft bg-elevated/30 px-4 py-6 text-center text-xs text-muted">
                  هنوز فعالیتی ثبت نشده است. ایجاد پروژه، صدور لایسنس و ارسال اطلاعیه در
                  این بخش ثبت می شود.
                </p>
              ) : (
                <ol className="space-y-0">
                  {data.recent_activity.map((entry, index, list) => (
                    <li
                      key={entry.id}
                      className={`flex gap-3 py-3 ${
                        index < list.length - 1 ? "border-b border-line-soft" : ""
                      }`}
                    >
                      <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-elevated text-[#b9a7ff]">
                        <BellRing size={13} aria-hidden />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs">
                          <span className="font-medium text-ink">
                            {entry.action_label ?? entry.action}
                          </span>{" "}
                          <span className="text-muted">توسط {entry.actor_label ?? entry.actor_type}</span>
                        </p>
                        <p className="mt-0.5 text-[10px] text-muted">
                          {formatDateTime(entry.created_at)} · {formatRelative(entry.created_at)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <div className="space-y-4">
              <section className="panel p-5">
                <h2 className="mb-3 text-sm font-semibold">وضعیت عملیاتی</h2>
                {system ? (
                  <dl className="space-y-2 text-[11px]">
                    <div className="flex items-center justify-between">
                      <dt className="text-muted">Worker</dt>
                      <dd>
                        <Badge
                          tone={system.worker.status === "online" ? "success" : "warning"}
                          dot
                        >
                          {system.worker.status === "online"
                            ? "در حال اجرا"
                            : system.worker.status === "offline"
                              ? "متوقف"
                              : "بدون گزارش"}
                        </Badge>
                      </dd>
                    </div>
                    <div className="flex items-center justify-between">
                      <dt className="text-muted">ربات تلگرام</dt>
                      <dd>
                        <Badge tone={system.telegram.mode === "http" ? "success" : "neutral"}>
                          {system.telegram.mode === "http" ? "واقعی" : "شبیه سازی"}
                        </Badge>
                      </dd>
                    </div>
                    <div className="flex items-center justify-between">
                      <dt className="text-muted">پایگاه داده</dt>
                      <dd>
                        <Badge tone={system.database.status === "ok" ? "success" : "danger"}>
                          {system.database.status === "ok"
                            ? `سالم · ${formatNumber(system.database.latency_ms ?? 0)}ms`
                            : "خطا"}
                        </Badge>
                      </dd>
                    </div>
                    <div className="flex items-center justify-between">
                      <dt className="text-muted">کارهای در صف / ناموفق</dt>
                      <dd className="font-medium text-ink">
                        {formatNumber(system.pending_jobs)} / {formatNumber(system.failed_jobs)}
                      </dd>
                    </div>
                  </dl>
                ) : (
                  <p className="text-[11px] leading-6 text-muted">
                    {status.error
                      ? errorMessage(status.error)
                      : "در حال دریافت وضعیت..."}
                  </p>
                )}
              </section>

              <section className="panel p-5">
                <h2 className="mb-3 text-sm font-semibold">اقدام های سریع</h2>
                <div className="space-y-1.5">
                  {[
                    { href: "/projects", label: "مدیریت پروژه ها", icon: FolderKanban },
                    { href: "/licenses", label: "لایسنس ها", icon: KeyRound },
                    { href: "/notifications", label: "تاریخچه ارسال", icon: BellRing },
                    { href: "/payments", label: "پرداخت ها", icon: Wallet },
                    { href: "/settings", label: "تنظیمات سیستم", icon: Settings },
                  ].map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="flex items-center gap-2.5 rounded-lg px-2 py-2 text-xs text-muted transition hover:bg-white/5 hover:text-ink"
                      >
                        <Icon size={14} aria-hidden />
                        <span className="flex-1">{item.label}</span>
                        <ArrowLeft size={12} aria-hidden />
                      </Link>
                    );
                  })}
                </div>
              </section>

              {data.pending_members > 0 || data.license_attention > 0 ? (
                <section className="panel border-warning/30 p-5">
                  <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <CalendarClock size={15} aria-hidden className="text-warning" />
                    نیازمند بررسی
                  </h2>
                  <p className="text-[11px] leading-6 text-muted">
                    {formatNumber(data.pending_members)} درخواست اتصال در انتظار تایید و{" "}
                    {formatNumber(data.license_attention)} لایسنس نزدیک انقضا وجود دارد.
                  </p>
                </section>
              ) : null}
              {refreshedAt ? (
                <p className="text-center text-[10px] text-muted" aria-live="polite">
                  آخرین به روزرسانی دستی: {formatDateTime(refreshedAt.toISOString())}
                </p>
              ) : null}
            </div>
          </div>
        </>
      )}
    </>
  );
}
