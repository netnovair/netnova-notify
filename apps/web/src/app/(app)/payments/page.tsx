"use client";

import { Plus, Wallet } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { PaymentStatusBadge } from "@/components/ui/StatusBadge";
import { PaymentActions } from "@/features/payments/PaymentActions";
import { PaymentFormModal } from "@/features/payments/PaymentFormModal";
import { api, queryString } from "@/lib/api";
import { formatAmount, formatDate, formatDateTime } from "@/lib/format";
import { PAYMENT_STATUS } from "@/lib/labels";
import { useApiData } from "@/lib/hooks";
import type { Page, Payment, ProjectListItem } from "@/types/api";

const PAGE_SIZE = 20;

function PaymentsContent() {
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Payment | null>(null);

  const payments = useApiData<Page<Payment>>(
    (signal) =>
      api.get<Page<Payment>>(
        `/payments${queryString({
          status,
          project_id: projectId,
          page,
          page_size: PAGE_SIZE,
        })}`,
        signal,
      ),
    [status, projectId, page],
  );

  const projects = useApiData<Page<ProjectListItem>>(
    (signal) => api.get<Page<ProjectListItem>>("/projects?page_size=100", signal),
    [],
  );

  const projectItems = projects.data?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="مدیریت"
        title="پرداخت ها"
        subtitle="وضعیت مالی پروژه ها؛ یادآوری ها به صورت خودکار زمان بندی می شوند و تراکنش بانکی تایید نمی شود."
        actions={
          <Button onClick={() => setCreateOpen(true)} disabled={projectItems.length === 0}>
            <Plus size={16} aria-hidden />
            ثبت پرداخت
          </Button>
        }
      />

      <div className="mb-4">
        <InlineAlert>
          این سیستم دریافت وجه آنلاین انجام نمی دهد. «تسویه شده» یعنی مدیر پرداخت را ثبت
          کرده است و سند بانکی به صورت خودکار بررسی نمی شود.
        </InlineAlert>
      </div>

      <div className="panel mb-4 flex flex-col gap-2 p-3 sm:flex-row">
        <select
          className="field-input sm:w-56"
          value={projectId}
          onChange={(event) => {
            setProjectId(event.target.value);
            setPage(1);
          }}
          aria-label="فیلتر پروژه"
        >
          <option value="">همه پروژه ها</option>
          {projectItems.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <select
          className="field-input sm:w-56"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          aria-label="فیلتر وضعیت پرداخت"
        >
          <option value="">همه وضعیت ها</option>
          {Object.entries(PAYMENT_STATUS).map(([key, value]) => (
            <option key={key} value={key}>
              {value.label}
            </option>
          ))}
        </select>
        {(status || projectId) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setStatus("");
              setProjectId("");
              setPage(1);
            }}
          >
            پاک کردن فیلترها
          </Button>
        )}
      </div>

      <div className="panel overflow-hidden">
        {payments.error && !payments.data ? (
          <ErrorState message={payments.error} onRetry={payments.reload} />
        ) : payments.loading && !payments.data ? (
          <SkeletonRows rows={6} />
        ) : payments.data && payments.data.items.length === 0 ? (
          <EmptyState
            icon={<Wallet size={24} aria-hidden />}
            title="پرداختی مطابق فیلتر یافت نشد"
            description={
              projectItems.length === 0
                ? "ابتدا یک پروژه ایجاد کنید، سپس وضعیت مالی آن را ثبت کنید."
                : "با ثبت پرداخت، یادآوری سررسید به صورت خودکار برای کارفرما زمان بندی می شود."
            }
            action={
              projectItems.length > 0 ? (
                <Button onClick={() => setCreateOpen(true)} disabled={projectItems.length === 0}>
                  <Plus size={15} aria-hidden />
                  ثبت پرداخت
                </Button>
              ) : null
            }
          />
        ) : payments.data ? (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>پروژه</th>
                    <th>عنوان</th>
                    <th>مبلغ</th>
                    <th>سررسید</th>
                    <th>وضعیت</th>
                    <th>یادآوری بعدی</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payments.data.items.map((payment) => (
                    <tr key={payment.id}>
                      <td className="text-xs text-muted">{payment.project_name ?? "—"}</td>
                      <td>
                        <p className="text-sm">{payment.title}</p>
                        <p className="text-[10px] text-muted">
                          ثبت {formatDate(payment.created_at)}
                        </p>
                      </td>
                      <td className="whitespace-nowrap text-xs">
                        {formatAmount(payment.amount_minor, payment.currency)}
                      </td>
                      <td className="whitespace-nowrap text-xs">{formatDate(payment.due_at)}</td>
                      <td>
                        <PaymentStatusBadge
                          status={payment.status}
                          isOverdue={payment.is_overdue}
                        />
                      </td>
                      <td className="text-xs text-muted">
                        {payment.status === "unpaid" ? (
                          payment.next_reminder_at ? (
                            formatDateTime(payment.next_reminder_at)
                          ) : (
                            <Badge tone="neutral">بدون یادآوری</Badge>
                          )
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <PaymentActions
                          payment={payment}
                          onEdit={() => setEditTarget(payment)}
                          onChanged={payments.reload}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-line-soft lg:hidden">
              {payments.data.items.map((payment) => (
                <li key={payment.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{payment.title}</p>
                      <p className="mt-0.5 text-[10px] text-muted">
                        {payment.project_name ?? "—"} · سررسید {formatDate(payment.due_at)}
                      </p>
                    </div>
                    <PaymentStatusBadge
                      status={payment.status}
                      isOverdue={payment.is_overdue}
                    />
                  </div>
                  <p className="mt-2 text-sm">{formatAmount(payment.amount_minor, payment.currency)}</p>
                  <div className="mt-3">
                    <PaymentActions
                      payment={payment}
                      onEdit={() => setEditTarget(payment)}
                      onChanged={payments.reload}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <Pagination page={payments.data} onChange={setPage} label="پرداخت" />
          </>
        ) : null}
      </div>

      {createOpen ? (
        <PaymentFormModal
          open
          onClose={() => setCreateOpen(false)}
          projects={projectItems}
          onSaved={() => payments.reload()}
        />
      ) : null}
      {editTarget ? (
        <PaymentFormModal
          open
          onClose={() => setEditTarget(null)}
          projects={projectItems}
          fixedProjectId={editTarget.project_id}
          payment={editTarget}
          onSaved={() => payments.reload()}
        />
      ) : null}
    </>
  );
}

export default function PaymentsPage() {
  return (
    <Suspense fallback={<div className="panel mt-10"><SkeletonRows rows={6} /></div>}>
      <PaymentsContent />
    </Suspense>
  );
}
