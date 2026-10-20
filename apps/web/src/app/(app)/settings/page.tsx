"use client";

import {
  Bot,
  Database,
  ExternalLink,
  KeyRound,
  LogOut,
  RefreshCw,
  ServerCog,
  ShieldAlert,
  TerminalSquare,
} from "lucide-react";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, InlineAlert, LoadingState } from "@/components/ui/States";
import { InstallCard } from "@/features/pwa/InstallCard";
import { AdminsCard } from "@/features/settings/AdminsCard";
import { DemoDataCard } from "@/features/settings/DemoDataCard";
import { ChannelsCard } from "@/features/settings/ChannelsCard";
import { PasswordCard } from "@/features/settings/PasswordCard";
import { api } from "@/lib/api";
import { formatDateTime, formatNumber, formatRelative } from "@/lib/format";
import { JOB_STATUS_LABELS, TELEGRAM_MODE_LABELS } from "@/lib/labels";
import { useApiData } from "@/lib/hooks";
import type { SystemStatus } from "@/types/api";

const API_BASE = "https://notify.example.com/api/v1";
const WEBHOOK_COMMAND = `cd apps/api\npython -m scripts.set_webhook --url ${API_BASE}/telegram/webhook`;
const WORKER_COMMAND = "cd apps/api\npython -m app.worker.main";

function StatusRow({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  hint?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line-soft py-2.5 last:border-b-0">
      <div>
        <p className="text-xs text-muted">{label}</p>
        {hint ? <p className="mt-0.5 text-[10px] text-muted/80">{hint}</p> : null}
      </div>
      <div className="text-end">
        <Badge tone={tone}>{value}</Badge>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { admin, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const status = useApiData<SystemStatus>((signal) =>
    api.get<SystemStatus>("/system/status", signal),
  );

  const data = status.data;
  const workerTone =
    data?.worker.status === "online"
      ? "success"
      : data?.worker.status === "offline"
        ? "danger"
        : "neutral";

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
  }

  return (
    <>
      <PageHeader
        eyebrow="سیستم"
        title="تنظیمات"
        subtitle="وضعیت اتصال ربات، Worker، پایگاه داده و راهنمای راه اندازی."
        actions={
          <Button variant="secondary" size="sm" onClick={status.reload}>
            <RefreshCw size={14} aria-hidden />
            به روزرسانی وضعیت
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel p-5">
          <div className="mb-3 flex items-center gap-2">
            <KeyRound size={17} className="text-[#b9a7ff]" aria-hidden />
            <h2 className="text-sm font-semibold">حساب مدیر</h2>
          </div>
          <dl className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-line-soft py-2">
              <dt className="text-muted">نام</dt>
              <dd>{admin?.display_name}</dd>
            </div>
            <div className="flex justify-between border-b border-line-soft py-2">
              <dt className="text-muted">ایمیل</dt>
              <dd dir="ltr">{admin?.email}</dd>
            </div>
            <div className="flex justify-between border-b border-line-soft py-2">
              <dt className="text-muted">آخرین ورود</dt>
              <dd>{formatDateTime(admin?.last_login_at)}</dd>
            </div>
            <div className="flex justify-between py-2">
              <dt className="text-muted">مدت نشست</dt>
              <dd>
                {data ? `${formatNumber(data.session_ttl_hours)} ساعت` : "—"}
              </dd>
            </div>
          </dl>
          <Button
            variant="danger"
            size="sm"
            className="mt-3"
            onClick={() => void handleLogout()}
            loading={loggingOut}
          >
            <LogOut size={14} aria-hidden />
            خروج از حساب
          </Button>
        </section>

        <PasswordCard admin={admin} />

        <AdminsCard currentAdminId={admin?.id ?? null} />

        <ChannelsCard />

        <DemoDataCard />

        <InstallCard />

        <section className="panel p-5 lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <ServerCog size={17} className="text-[#b9a7ff]" aria-hidden />
            <h2 className="text-sm font-semibold">وضعیت سیستم</h2>
            {data ? (
              <span className="ms-auto text-[10px] text-muted">
                {formatRelative(data.server_time)} · {formatDateTime(data.server_time)}
              </span>
            ) : null}
          </div>

          {status.error && !data ? (
            <ErrorState message={status.error} onRetry={status.reload} compact />
          ) : status.loading && !data ? (
            <LoadingState compact />
          ) : data ? (
            <div className="grid gap-x-8 sm:grid-cols-2">
              <div>
                <StatusRow
                  label="پایگاه داده"
                  value={
                    data.database.status === "ok"
                      ? `سالم · ${formatNumber(data.database.latency_ms ?? 0)} میلی ثانیه`
                      : "خطا"
                  }
                  tone={data.database.status === "ok" ? "success" : "danger"}
                  hint={`موتور: ${data.database.dialect}`}
                />
                <StatusRow
                  label="Worker"
                  value={JOB_STATUS_LABELS[data.worker.status] ?? data.worker.status}
                  tone={workerTone}
                  hint={
                    data.worker.last_seen_at
                      ? `آخرین گزارش: ${formatDateTime(data.worker.last_seen_at)}`
                      : "Worker هنوز گزارشی ثبت نکرده است"
                  }
                />
                <StatusRow
                  label="کارهای در صف / ناموفق"
                  value={`${formatNumber(data.pending_jobs)} / ${formatNumber(data.failed_jobs)}`}
                  tone={data.failed_jobs > 0 ? "warning" : "neutral"}
                />
              </div>
              <div>
                <StatusRow
                  label="تلگرام"
                  value={TELEGRAM_MODE_LABELS[data.telegram.mode] ?? data.telegram.mode}
                  tone={data.telegram.mode === "http" ? "success" : "info"}
                  hint={
                    data.telegram.mode === "mock"
                      ? "پیام ها واقعی ارسال نمی شوند"
                      : "توکن ربات روی سرور تنظیم شده است"
                  }
                />
                <StatusRow
                  label="Secret وب هوک"
                  value={data.telegram.webhook_secret_configured ? "تنظیم شده" : "تنظیم نشده"}
                  tone={data.telegram.webhook_secret_configured ? "success" : "danger"}
                />
                <StatusRow
                  label="آخرین به روزرسانی تلگرام"
                  value={
                    data.telegram.last_update_at
                      ? formatRelative(data.telegram.last_update_at)
                      : "دریافت نشده"
                  }
                  tone="neutral"
                />
              </div>
            </div>
          ) : null}

          {data ? (
            <div className="mt-4 grid gap-2 rounded-xl border border-line-soft bg-elevated/40 p-3 text-[11px] sm:grid-cols-2">
              <p>
                محیط: <span className="text-ink">{data.environment}</span>
              </p>
              <p>
                منطقه زمانی: <span className="text-ink">{data.timezone}</span>
              </p>
              <p>
                یادآوری پرداخت:{" "}
                <span className="text-ink">
                  {formatNumber(data.payment_reminder_days_before)} روز قبل از سررسید
                </span>
              </p>
              <p>
                HTTPS الزامی:{" "}
                <span className="text-ink">{data.https_required ? "بله" : "خیر (توسعه)"}</span>
              </p>
            </div>
          ) : null}

          {data?.telegram.mode === "mock" ? (
            <div className="mt-3">
              <InlineAlert tone="info">
                در حالت شبیه سازی، ارسال ها در پایگاه داده با نشانه Mock ثبت می شوند و
                هیچ پیامی به تلگرام واقعی نمی رود.
              </InlineAlert>
            </div>
          ) : null}
        </section>

        <section className="panel p-5 lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <Bot size={17} className="text-[#b9a7ff]" aria-hidden />
            <h2 className="text-sm font-semibold">راهنمای اتصال ربات و Worker</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-line bg-elevated/40 p-3.5">
              <p className="mb-2 text-xs font-medium">ثبت Webhook تلگرام</p>
              <pre
                dir="ltr"
                className="overflow-x-auto rounded-lg bg-bg/80 p-3 text-left text-[10px] leading-6 text-[#cdd6ee]"
              >
                {WEBHOOK_COMMAND}
              </pre>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <CopyButton value={WEBHOOK_COMMAND} label="کپی دستور" />
                <span className="text-[10px] text-muted">
                  مسیر پیشنهادی: <code dir="ltr">{data?.telegram.webhook_path}</code>
                </span>
              </div>
              <p className="mt-2 text-[10px] leading-6 text-muted">
                آدرس باید HTTPS معتبر باشد. توکن ربات فقط از متغیرهای محیطی خوانده می شود و
                در رابط کاربری نمایش داده نمی شود.
              </p>
            </div>

            <div className="rounded-xl border border-line bg-elevated/40 p-3.5">
              <p className="mb-2 text-xs font-medium">اجرای Worker</p>
              <pre
                dir="ltr"
                className="overflow-x-auto rounded-lg bg-bg/80 p-3 text-left text-[10px] leading-6 text-[#cdd6ee]"
              >
                {WORKER_COMMAND}
              </pre>
              <div className="mt-2">
                <CopyButton value={WORKER_COMMAND} label="کپی دستور" />
              </div>
              <p className="mt-2 text-[10px] leading-6 text-muted">
                Worker سرویس مستقل است و پس از restart کارهای پردازش نشده را از صف پایدار
                ادامه می دهد. برای بررسی یک باره صف می توانید از{" "}
                <code dir="ltr">--once</code> استفاده کنید.
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-2 text-[10px] leading-6 text-muted sm:grid-cols-2">
            <p className="flex items-start gap-2">
              <Database size={13} className="mt-1 shrink-0" aria-hidden />
              پشتیبان گیری: از پایگاه داده PostgreSQL با pg_dump نسخه پشتیبان تهیه کنید و
              فایل را خارج از سرور نگهداری کنید.
            </p>
            <p className="flex items-start gap-2">
              <ShieldAlert size={13} className="mt-1 shrink-0" aria-hidden />
              هرگز فایل .env، توکن ربات یا کد لایسنس را در GitHub یا پیام های عمومی قرار
              ندهید.
            </p>
            <p className="flex items-start gap-2">
              <TerminalSquare size={13} className="mt-1 shrink-0" aria-hidden />
              مستندات کامل: docs/deployment.md و docs/local-setup-windows.md در مخزن.
            </p>
            <p className="flex items-start gap-2">
              <ExternalLink size={13} className="mt-1 shrink-0" aria-hidden />
              مستندات API فقط در محیط توسعه در مسیر <code dir="ltr">/api/docs</code>
              فعال است و در استقرار عملیاتی غیرفعال می شود.
            </p>
          </div>
        </section>
      </div>

      <p className="mt-6 text-center text-[10px] text-muted">
        NetNova Notify · نسخه MVP · وضعیت ها از API واقعی خوانده می شوند
      </p>
    </>
  );
}
