"use client";

import {
  BellRing,
  CheckCircle2,
  CircleSlash,
  KeyRound,
  Send,
  Wallet,
} from "lucide-react";

import { Badge, DemoBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineAlert } from "@/components/ui/States";
import { LicenseStatusBadge, ProjectStatusBadge } from "@/components/ui/StatusBadge";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";
import { FEATURE_LABELS } from "@/lib/labels";
import type { Project } from "@/types/api";

export type ProjectTabKey =
  | "overview"
  | "license"
  | "members"
  | "notifications"
  | "payments"
  | "tickets"
  | "capabilities"
  | "activity";

export function OverviewTab({
  project,
  onNavigate,
  onNewNotification,
  onNewPayment,
}: {
  project: Project;
  onNavigate: (tab: ProjectTabKey) => void;
  onNewNotification: () => void;
  onNewPayment: () => void;
}) {
  const employer = project.members.find((member) => member.status === "active") ?? null;
  const pendingCount = project.members.filter(
    (member) => member.status === "pending_approval",
  ).length;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="panel p-5 lg:col-span-2">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">اطلاعات اصلی</h2>
          <ProjectStatusBadge status={project.status} />
          {project.is_demo ? <DemoBadge /> : null}
        </div>
        <p className="prose-persian mb-5 text-sm leading-8 text-muted">
          {project.description || "برای این پروژه توضیحی ثبت نشده است."}
        </p>
        <dl className="grid gap-x-8 gap-y-3 text-xs sm:grid-cols-2">
          {[
            ["کارفرما", project.client_name],
            ["شناسه انگلیسی", project.slug],
            ["تاریخ ایجاد", formatDate(project.created_at)],
            ["آخرین تغییر", formatDateTime(project.updated_at)],
            [
              "اتصال تلگرام",
              employer ? `متصل به ${employer.display_name}` : "کارفرمای متصل وجود ندارد",
            ],
            [
              "زمان اتصال",
              project.telegram_connected_at
                ? formatDateTime(project.telegram_connected_at)
                : "—",
            ],
          ].map(([label, value]) => (
            <div
              key={label}
              className="flex items-start justify-between gap-4 border-b border-line-soft py-2"
            >
              <dt className="shrink-0 text-muted">{label}</dt>
              <dd className="text-end text-ink" dir={label === "شناسه انگلیسی" ? "ltr" : undefined}>
                {value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-5 grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-line-soft bg-elevated/40 p-3 text-center">
            <BellRing size={15} className="mx-auto mb-1 text-[#b9a7ff]" aria-hidden />
            <p className="text-base font-semibold">{formatNumber(project.notifications_count)}</p>
            <p className="text-[10px] text-muted">اطلاعیه</p>
          </div>
          <div className="rounded-xl border border-line-soft bg-elevated/40 p-3 text-center">
            <Wallet size={15} className="mx-auto mb-1 text-[#b9a7ff]" aria-hidden />
            <p className="text-base font-semibold">{formatNumber(project.open_payments_count)}</p>
            <p className="text-[10px] text-muted">پرداخت باز</p>
          </div>
          <div className="rounded-xl border border-line-soft bg-elevated/40 p-3 text-center">
            <KeyRound size={15} className="mx-auto mb-1 text-[#b9a7ff]" aria-hidden />
            <p className="text-[10px] leading-7 text-muted">
              {project.license ? (
                <LicenseStatusBadge status={project.license.effective_status} />
              ) : (
                <Badge tone="danger">بدون لایسنس</Badge>
              )}
            </p>
          </div>
        </div>

        {pendingCount > 0 ? (
          <div className="mt-4">
            <InlineAlert tone="warning">
              {formatNumber(pendingCount)} درخواست اتصال کارفرما در انتظار تایید شماست.{" "}
              <button
                type="button"
                onClick={() => onNavigate("members")}
                className="underline underline-offset-2"
              >
                بررسی درخواست ها
              </button>
            </InlineAlert>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2">
          <Button size="sm" onClick={onNewNotification}>
            <Send size={14} aria-hidden />
            اطلاعیه جدید
          </Button>
          <Button size="sm" variant="secondary" onClick={onNewPayment}>
            <Wallet size={14} aria-hidden />
            ثبت پرداخت
          </Button>
          <Button size="sm" variant="ghost" onClick={() => onNavigate("license")}>
            <KeyRound size={14} aria-hidden />
            مدیریت لایسنس
          </Button>
        </div>
      </section>

      <section className="panel h-fit">
        <div className="border-b border-line px-4 py-3.5">
          <h2 className="text-sm font-semibold">قابلیت های فعال</h2>
          <p className="mt-0.5 text-[10px] text-muted">این فهرست منوی تلگرام کارفرما را می سازد.</p>
        </div>
        <ul className="divide-y divide-line-soft">
          {project.features.map((feature) => (
            <li key={feature.key} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="flex items-center gap-2">
                {feature.enabled ? (
                  <CheckCircle2 size={15} className="text-success" aria-hidden />
                ) : (
                  <CircleSlash size={15} className="text-muted" aria-hidden />
                )}
                <span className={feature.enabled ? "text-sm" : "text-sm text-muted"}>
                  {FEATURE_LABELS[feature.key] ?? feature.label}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {!feature.implemented ? <Badge tone="neutral">به زودی</Badge> : null}
                <Badge tone={feature.enabled ? "success" : "neutral"}>
                  {feature.enabled ? "روشن" : "خاموش"}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
        <div className="border-t border-line px-4 py-3">
          <p className="text-[10px] leading-6 text-muted">
            تغییر قابلیت ها از دکمه ویرایش پروژه انجام می شود و بلافاصله در منوی ربات اعمال
            می شود.
          </p>
        </div>
      </section>
    </div>
  );
}
