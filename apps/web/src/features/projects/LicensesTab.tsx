"use client";

import { AlertTriangle, KeyRound, Plus } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { CopyButton } from "@/components/ui/CopyButton";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { LicenseStatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { LicenseIssueModal } from "@/features/licenses/LicenseIssueModal";
import { LicenseRevealModal } from "@/features/licenses/LicenseRevealModal";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { License, LicenseCreated, Project, ProjectListItem } from "@/types/api";

export function LicensesTab({
  project,
  refreshToken,
  onProjectChanged,
}: {
  project: Project;
  refreshToken: number;
  onProjectChanged: () => void;
}) {
  const { notify } = useToast();
  const [issueOpen, setIssueOpen] = useState(false);
  const [revealed, setRevealed] = useState<LicenseCreated | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<License | null>(null);
  const [busy, setBusy] = useState(false);

  const licenses = useApiData<License[]>(
    (signal) => api.get<License[]>(`/projects/${project.id}/licenses`, signal),
    [project.id, refreshToken],
  );

  const projectAsList: ProjectListItem[] = [
    {
      ...project,
      telegram_connected: project.members.some((member) => member.status === "active"),
      employer: project.members.find((member) => member.status === "active") ?? null,
      license_status: project.license?.effective_status ?? null,
      license_expires_at: project.license?.expires_at ?? null,
      enabled_features: project.features.filter((item) => item.enabled).map((item) => item.key),
    },
  ];

  async function revoke() {
    if (!revokeTarget) return;
    setBusy(true);
    try {
      await api.post(`/licenses/${revokeTarget.id}/revoke`, { reason: "admin_revoked" });
      notify("لایسنس لغو شد و دسترسی کارفرما متوقف شد.", "success");
      setRevokeTarget(null);
      licenses.reload();
      onProjectChanged();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <KeyRound size={16} className="text-[#b9a7ff]" aria-hidden />
            لایسنس جاری
          </h2>
          <p className="mt-1 text-[11px] leading-6 text-muted">
            کد کامل لایسنس فقط هنگام صدور نمایش داده می شود؛ در پایگاه داده فقط هش آن ذخیره
            است.
          </p>
        </div>
        <Button size="sm" onClick={() => setIssueOpen(true)}>
          <Plus size={14} aria-hidden />
          صدور لایسنس جدید
        </Button>
      </div>

      {project.license ? (
        <div className="panel p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <LicenseStatusBadge status={project.license.effective_status} />
              <code dir="ltr" className="rounded-md bg-elevated px-2 py-1 text-xs text-muted">
                {project.license.code_prefix}••••••••
              </code>
            </div>
            <span className="text-[11px] text-muted">
              صادر شده: {formatDate(project.license.created_at)}
            </span>
          </div>
          <dl className="mt-4 grid gap-x-8 gap-y-2 text-xs sm:grid-cols-3">
            <div>
              <dt className="text-muted">تاریخ انقضا</dt>
              <dd className="mt-0.5">{formatDate(project.license.expires_at)}</dd>
            </div>
            <div>
              <dt className="text-muted">زمان فعال سازی</dt>
              <dd className="mt-0.5">{formatDateTime(project.license.activated_at)}</dd>
            </div>
            <div>
              <dt className="text-muted">زمان لغو</dt>
              <dd className="mt-0.5">{formatDateTime(project.license.revoked_at)}</dd>
            </div>
          </dl>
          {project.license.effective_status === "active" ? (
            <div className="mt-4">
              <Button
                size="sm"
                variant="danger"
                onClick={() => setRevokeTarget(project.license)}
              >
                لغو لایسنس
              </Button>
            </div>
          ) : null}
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-warning/20 bg-warning/[0.04] px-3 py-2.5 text-[10px] leading-6 text-[#f5d992]">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden />
            لغو لایسنس، دسترسی عملیاتی کارفرمای متصل را متوقف می کند. صدور لایسنس جدید
            لایسنس فعال قبلی را لغو می کند ولی اتصال کارفرما حفظ می شود.
          </div>
        </div>
      ) : (
        <div className="panel border-dashed">
          <EmptyState
            icon={<KeyRound size={22} aria-hidden />}
            title="لایسنس فعالی وجود ندارد"
            description="برای اتصال کارفرما، یک لایسنس جدید برای این پروژه صادر کنید."
            action={
              <Button size="sm" onClick={() => setIssueOpen(true)}>
                صدور لایسنس
              </Button>
            }
          />
        </div>
      )}

      <section className="panel overflow-hidden">
        <div className="border-b border-line px-4 py-3.5">
          <h2 className="text-sm font-semibold">تاریخچه لایسنس ها</h2>
        </div>
        {licenses.error && !licenses.data ? (
          <ErrorState message={licenses.error} onRetry={licenses.reload} compact />
        ) : licenses.loading && !licenses.data ? (
          <SkeletonRows rows={3} />
        ) : licenses.data && licenses.data.length === 0 ? (
          <EmptyState title="لایسنسی صادر نشده است" />
        ) : licenses.data ? (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[640px]">
              <thead>
                <tr>
                  <th>پیشوند کد</th>
                  <th>وضعیت</th>
                  <th>صدور</th>
                  <th>انقضا</th>
                  <th>فعال سازی</th>
                  <th>لغو</th>
                </tr>
              </thead>
              <tbody>
                {licenses.data.map((license) => (
                  <tr key={license.id}>
                    <td>
                      <Badge tone="neutral">
                        <span dir="ltr">{license.code_prefix}•••</span>
                      </Badge>
                    </td>
                    <td>
                      <LicenseStatusBadge status={license.effective_status} />
                    </td>
                    <td className="text-xs">{formatDate(license.created_at)}</td>
                    <td className="text-xs">{formatDate(license.expires_at)}</td>
                    <td className="text-xs">{formatDateTime(license.activated_at)}</td>
                    <td className="text-xs">{formatDateTime(license.revoked_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <div className="panel p-4">
        <p className="mb-2 text-xs text-muted">اطلاعات قابل اشتراک با کارفرما</p>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="text-muted">شناسه پروژه:</span>
          <code dir="ltr" className="rounded bg-elevated px-2 py-1">
            {project.slug}
          </code>
          <CopyButton value={project.slug} label="کپی شناسه" variant="ghost" />
        </div>
        <p className="mt-2 text-[10px] leading-6 text-muted">
          کد کامل لایسنس پس از صدور فقط یک بار در پنجره صدور نمایش داده می شود و در این
          صفحه قابل بازیابی نیست.
        </p>
      </div>

      {issueOpen ? (
        <LicenseIssueModal
          open
          onClose={() => setIssueOpen(false)}
          projects={projectAsList}
          fixedProjectId={project.id}
          onIssued={(license) => {
            setRevealed(license);
            licenses.reload();
            onProjectChanged();
          }}
        />
      ) : null}
      <LicenseRevealModal
        open={Boolean(revealed)}
        onClose={() => setRevealed(null)}
        code={revealed?.code ?? null}
        projectName={project.name}
      />
      <ConfirmDialog
        open={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        onConfirm={revoke}
        loading={busy}
        tone="danger"
        title="لغو لایسنس"
        message="با لغو لایسنس، کد فعلی دیگر قابل استفاده نیست و دسترسی کارفرمای متصل به این پروژه متوقف می شود. این عملیات در تاریخچه فعالیت ثبت می شود."
        confirmLabel="لغو لایسنس"
      />
    </div>
  );
}
