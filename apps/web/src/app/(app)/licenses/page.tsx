"use client";

import { KeyRound, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { LicenseStatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { LicenseIssueModal } from "@/features/licenses/LicenseIssueModal";
import { LicenseRevealModal } from "@/features/licenses/LicenseRevealModal";
import { api, errorMessage, queryString } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { LICENSE_STATUS } from "@/lib/labels";
import { useApiData } from "@/lib/hooks";
import type {
  License,
  LicenseCreated,
  LicenseStatus,
  Page,
  ProjectListItem,
} from "@/types/api";

export default function LicensesPage() {
  const { notify } = useToast();
  const [status, setStatus] = useState<string>("");
  const [page, setPage] = useState(1);
  const [issueOpen, setIssueOpen] = useState(false);
  const [fixedProjectId, setFixedProjectId] = useState<string | undefined>(undefined);
  const [revealed, setRevealed] = useState<LicenseCreated | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<License | null>(null);
  const [busy, setBusy] = useState(false);

  const licenses = useApiData<Page<License>>(
    (signal) =>
      api.get<Page<License>>(
        `/licenses${queryString({ status, page, page_size: 20 })}`,
        signal,
      ),
    [status, page],
  );

  const projects = useApiData<Page<ProjectListItem>>(
    (signal) => api.get<Page<ProjectListItem>>("/projects?page_size=100", signal),
    [],
  );

  async function revoke() {
    if (!revokeTarget) return;
    setBusy(true);
    try {
      await api.post(`/licenses/${revokeTarget.id}/revoke`, { reason: "admin_revoked" });
      notify("لایسنس لغو شد و دسترسی مرتبط با آن متوقف شد.", "success");
      setRevokeTarget(null);
      licenses.reload();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  const projectItems = projects.data?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="مدیریت"
        title="لایسنس ها"
        subtitle="هر پروژه یک لایسنس مستقل دارد. کد خام فقط هنگام صدور نمایش داده می شود."
        actions={
          <Button
            onClick={() => {
              setFixedProjectId(undefined);
              setIssueOpen(true);
            }}
          >
            <Plus size={16} aria-hidden />
            صدور لایسنس
          </Button>
        }
      />

      <div className="mb-4">
        <InlineAlert>
          کد لایسنس با یک الگوریتم hash کلیددار ذخیره می شود و از پایگاه داده قابل بازیابی
          نیست. در صورت مفقود شدن کد، لایسنس جدید صادر کنید؛ لایسنس قبلی لغو می شود ولی
          اتصال کارفرما حفظ می شود.
        </InlineAlert>
      </div>

      <div className="panel mb-4 flex flex-wrap items-center gap-2 p-3">
        <button
          type="button"
          onClick={() => {
            setStatus("");
            setPage(1);
          }}
          className={`rounded-lg px-3 py-1.5 text-xs transition ${
            status === "" ? "bg-accent/15 text-ink ring-1 ring-inset ring-accent/25" : "text-muted hover:bg-white/5"
          }`}
        >
          همه
        </button>
        {(Object.keys(LICENSE_STATUS) as LicenseStatus[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => {
              setStatus(key);
              setPage(1);
            }}
            className={`rounded-lg px-3 py-1.5 text-xs transition ${
              status === key
                ? "bg-accent/15 text-ink ring-1 ring-inset ring-accent/25"
                : "text-muted hover:bg-white/5"
            }`}
          >
            {LICENSE_STATUS[key].label}
          </button>
        ))}
        <Button
          variant="ghost"
          size="sm"
          className="ms-auto"
          onClick={() => {
            licenses.reload();
            projects.reload();
          }}
        >
          <RefreshCw size={14} aria-hidden />
          به روزرسانی
        </Button>
      </div>

      <div className="panel overflow-hidden">
        {licenses.error && !licenses.data ? (
          <ErrorState message={licenses.error} onRetry={licenses.reload} />
        ) : licenses.loading && !licenses.data ? (
          <SkeletonRows rows={6} />
        ) : licenses.data && licenses.data.items.length === 0 ? (
          <EmptyState
            icon={<KeyRound size={24} aria-hidden />}
            title={status ? "لایسنسی با این وضعیت وجود ندارد" : "لایسنسی صادر نشده است"}
            description={
              status
                ? "وضعیت دیگری را انتخاب کنید."
                : "با ایجاد پروژه، لایسنس به صورت خودکار صادر می شود. می توانید از این صفحه هم لایسنس جدید صادر کنید."
            }
            action={
              <Button
                onClick={() => {
                  setFixedProjectId(undefined);
                  setIssueOpen(true);
                }}
                disabled={projectItems.length === 0}
              >
                <Plus size={15} aria-hidden />
                صدور لایسنس
              </Button>
            }
          />
        ) : licenses.data ? (
          <>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[800px]">
                <thead>
                  <tr>
                    <th>پروژه</th>
                    <th>پیشوند</th>
                    <th>وضعیت</th>
                    <th>صدور</th>
                    <th>انقضا</th>
                    <th>فعال سازی</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {licenses.data.items.map((license) => (
                    <tr key={license.id}>
                      <td className="text-sm">{license.project_name ?? "—"}</td>
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
                      <td>
                        <div className="flex items-center gap-1.5">
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => {
                              setFixedProjectId(license.project_id);
                              setIssueOpen(true);
                            }}
                          >
                            صدور مجدد
                          </Button>
                          {license.effective_status === "active" ||
                          license.effective_status === "pending" ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setRevokeTarget(license)}
                            >
                              لغو
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={licenses.data} onChange={setPage} label="لایسنس" />
          </>
        ) : null}
      </div>

      {issueOpen ? (
        <LicenseIssueModal
          open
          onClose={() => setIssueOpen(false)}
          projects={projectItems}
          fixedProjectId={fixedProjectId}
          onIssued={(license) => {
            setRevealed(license);
            licenses.reload();
          }}
        />
      ) : null}
      <LicenseRevealModal
        open={Boolean(revealed)}
        onClose={() => setRevealed(null)}
        code={revealed?.code ?? null}
        projectName={
          projectItems.find((project) => project.id === revealed?.project_id)?.name
        }
      />
      <ConfirmDialog
        open={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        onConfirm={revoke}
        loading={busy}
        tone="danger"
        title="لغو لایسنس"
        message="کد این لایسنس دیگر قابل استفاده نیست و دسترسی کارفرمای متصل به پروژه متوقف می شود. لایسنس جدید را می توانید از دکمه صدور مجدد بسازید."
        confirmLabel="لغو لایسنس"
      />
    </>
  );
}
