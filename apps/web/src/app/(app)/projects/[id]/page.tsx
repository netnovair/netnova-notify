"use client";

import clsx from "clsx";
import {
  ArrowRight,
  BellRing,
  Boxes,
  FolderOpen,
  KeyRound,
  MessagesSquare,
  Pencil,
  Power,
  Send,
  Users,
  Wallet,
  Activity,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { DemoBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { ProjectStatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { NotificationFormModal } from "@/features/notifications/NotificationFormModal";
import { PaymentFormModal } from "@/features/payments/PaymentFormModal";
import { ActivityTab } from "@/features/projects/ActivityTab";
import { CapabilitiesTab } from "@/features/projects/CapabilitiesTab";
import { ProjectTicketsTab } from "@/features/projects/ProjectTicketsTab";
import { LicensesTab } from "@/features/projects/LicensesTab";
import { MembersTab } from "@/features/projects/MembersTab";
import { NotificationsTab } from "@/features/projects/NotificationsTab";
import { OverviewTab, type ProjectTabKey } from "@/features/projects/OverviewTab";
import { PaymentsTab } from "@/features/projects/PaymentsTab";
import { ProjectFormModal } from "@/features/projects/ProjectFormModal";
import { api, errorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { Project, ProjectListItem } from "@/types/api";

const TABS: Array<{ key: ProjectTabKey; label: string; icon: typeof FolderOpen }> = [
  { key: "overview", label: "اطلاعات اصلی", icon: FolderOpen },
  { key: "license", label: "لایسنس", icon: KeyRound },
  { key: "members", label: "کاربران مجاز", icon: Users },
  { key: "notifications", label: "اطلاعیه ها", icon: BellRing },
  { key: "payments", label: "پرداخت ها", icon: Wallet },
  { key: "tickets", label: "پشتیبانی", icon: MessagesSquare },
  { key: "capabilities", label: "قابلیت ها و کانال ها", icon: Boxes },
  { key: "activity", label: "تاریخچه فعالیت", icon: Activity },
];

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = Array.isArray(params.id) ? params.id[0] : params.id;
  const { notify } = useToast();

  const project = useApiData<Project>(
    (signal) => api.get<Project>(`/projects/${projectId}`, signal),
    [projectId],
  );

  const [tab, setTab] = useState<ProjectTabKey>("overview");
  const [refreshToken, setRefreshToken] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [toggleOpen, setToggleOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  function refreshAll() {
    setRefreshToken((value) => value + 1);
    project.reload();
  }

  async function toggleStatus() {
    if (!project.data) return;
    const nextStatus = project.data.status === "active" ? "inactive" : "active";
    setBusy(true);
    try {
      await api.patch(`/projects/${projectId}`, { status: nextStatus });
      notify(
        nextStatus === "active"
          ? "پروژه فعال شد."
          : "پروژه غیرفعال شد و ارسال های در صف لغو شدند.",
        "success",
      );
      refreshAll();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
      setToggleOpen(false);
    }
  }

  const data = project.data;
  const projectAsList: ProjectListItem[] = data
    ? [
        {
          ...data,
          telegram_connected: data.members.some((member) => member.status === "active"),
          employer: data.members.find((member) => member.status === "active") ?? null,
          license_status: data.license?.effective_status ?? null,
          license_expires_at: data.license?.expires_at ?? null,
          enabled_features: data.features.filter((item) => item.enabled).map((item) => item.key),
        },
      ]
    : [];

  return (
    <>
      <Link
        href="/projects"
        className="mb-4 inline-flex items-center gap-1.5 text-[11px] text-muted transition hover:text-ink"
      >
        <ArrowRight size={13} aria-hidden />
        بازگشت به پروژه ها
      </Link>

      {project.error && !data ? (
        <div className="panel">
          <ErrorState message={project.error} onRetry={project.reload} />
        </div>
      ) : project.loading && !data ? (
        <div className="space-y-4">
          <div className="panel p-6">
            <div className="skeleton mb-3 h-6 w-56" />
            <div className="skeleton h-3 w-40" />
          </div>
          <div className="panel">
            <SkeletonRows rows={5} />
          </div>
        </div>
      ) : data ? (
        <>
          <header className="mb-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-xl font-semibold sm:text-2xl">{data.name}</h1>
                  <ProjectStatusBadge status={data.status} />
                  {data.is_demo ? <DemoBadge /> : null}
                  {data.archived_at ? <DemoBadge label="بایگانی شده" /> : null}
                </div>
                <p className="mt-1 text-sm text-muted">
                  کارفرما: {data.client_name} ·{" "}
                  {formatNumber(data.notifications_count)} اطلاعیه ·{" "}
                  {formatNumber(data.open_payments_count)} پرداخت باز
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => setEditOpen(true)}>
                  <Pencil size={14} aria-hidden />
                  ویرایش
                </Button>
                <Button
                  size="sm"
                  variant={data.status === "active" ? "danger" : "secondary"}
                  onClick={() => setToggleOpen(true)}
                >
                  <Power size={14} aria-hidden />
                  {data.status === "active" ? "غیرفعال کردن" : "فعال کردن"}
                </Button>
                <Button
                  size="sm"
                  onClick={() => setNotificationOpen(true)}
                  disabled={Boolean(data.archived_at)}
                  title={data.archived_at ? "پروژه بایگانی شده است." : undefined}
                >
                  <Send size={14} aria-hidden />
                  اطلاعیه جدید
                </Button>
              </div>
            </div>
          </header>

          <div
            role="tablist"
            aria-label="بخش های پروژه"
            className="no-scrollbar mb-4 flex gap-1 overflow-x-auto rounded-xl border border-line bg-surface/60 p-1"
          >
            {TABS.map((item) => {
              const Icon = item.icon;
              const active = tab === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  role="tab"
                  id={`tab-${item.key}`}
                  aria-selected={active}
                  aria-controls={`panel-${item.key}`}
                  onClick={() => setTab(item.key)}
                  className={clsx(
                    "inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-xs transition",
                    active
                      ? "bg-accent/15 text-ink ring-1 ring-inset ring-accent/25"
                      : "text-muted hover:bg-white/5 hover:text-ink",
                  )}
                >
                  <Icon size={14} aria-hidden />
                  {item.label}
                </button>
              );
            })}
          </div>

          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "overview" ? (
              <OverviewTab
                project={data}
                onNavigate={setTab}
                onNewNotification={() => setNotificationOpen(true)}
                onNewPayment={() => setPaymentOpen(true)}
              />
            ) : tab === "license" ? (
              <LicensesTab
                project={data}
                refreshToken={refreshToken}
                onProjectChanged={refreshAll}
              />
            ) : tab === "members" ? (
              <MembersTab
                project={data}
                refreshToken={refreshToken}
                onProjectChanged={refreshAll}
              />
            ) : tab === "notifications" ? (
              <NotificationsTab
                project={data}
                refreshToken={refreshToken}
                onProjectChanged={refreshAll}
                onNewNotification={() => setNotificationOpen(true)}
              />
            ) : tab === "tickets" ? (
              <ProjectTicketsTab project={data} />
            ) : tab === "capabilities" ? (
              <CapabilitiesTab
                project={data}
                refreshToken={refreshToken}
                onProjectChanged={refreshAll}
                onDeleted={() => router.replace("/projects")}
              />
            ) : tab === "payments" ? (
              <PaymentsTab
                project={data}
                refreshToken={refreshToken}
                onProjectChanged={refreshAll}
                onNewPayment={() => setPaymentOpen(true)}
              />
            ) : (
              <ActivityTab project={data} refreshToken={refreshToken} />
            )}
          </div>

          {editOpen ? (
            <ProjectFormModal
              open
              onClose={() => setEditOpen(false)}
              project={data}
              onSaved={() => {
                notify("تغییرات پروژه ذخیره شد.", "success");
                refreshAll();
              }}
            />
          ) : null}
          {notificationOpen ? (
            <NotificationFormModal
              open
              onClose={() => setNotificationOpen(false)}
              project={{ id: data.id, name: data.name, channels: data.channels }}
              onCreated={() => {
                setTab("notifications");
                refreshAll();
              }}
            />
          ) : null}
          {paymentOpen ? (
            <PaymentFormModal
              open
              onClose={() => setPaymentOpen(false)}
              projects={projectAsList}
              fixedProjectId={data.id}
              onSaved={() => {
                setTab("payments");
                refreshAll();
              }}
            />
          ) : null}
          <ConfirmDialog
            open={toggleOpen}
            onClose={() => setToggleOpen(false)}
            onConfirm={toggleStatus}
            loading={busy}
            tone={data.status === "active" ? "danger" : "primary"}
            title={data.status === "active" ? "غیرفعال کردن پروژه" : "فعال کردن پروژه"}
            message={
              data.status === "active"
                ? "با غیرفعال شدن پروژه، دسترسی کارفرما متوقف می شود و اطلاعیه های در صف و یادآوری های زمان بندی شده لغو می شوند. لایسنس و اطلاعات پروژه حفظ می شود."
                : "پروژه فعال می شود و در صورت معتبر بودن لایسنس، کارفرمای متصل دوباره به منو دسترسی پیدا می کند."
            }
            confirmLabel={data.status === "active" ? "غیرفعال کن" : "فعال کن"}
          />
        </>
      ) : (
        <div className="panel">
          <EmptyState
            title="پروژه یافت نشد"
            description="ممکن است پروژه حذف شده باشد یا نشانی صفحه نادرست باشد."
            action={
              <Link href="/projects">
                <Button variant="secondary">بازگشت به پروژه ها</Button>
              </Link>
            }
          />
        </div>
      )}
    </>
  );
}
