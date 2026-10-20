"use client";

import { Plus, Wallet } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { PaymentStatusBadge } from "@/components/ui/StatusBadge";
import { PaymentActions } from "@/features/payments/PaymentActions";
import { PaymentFormModal } from "@/features/payments/PaymentFormModal";
import { api, queryString } from "@/lib/api";
import { formatAmount, formatDate, formatDateTime } from "@/lib/format";
import { PAYMENT_STATUS } from "@/lib/labels";
import { useApiData } from "@/lib/hooks";
import Link from "next/link";

import type {
  Currency,
  CurrencyTotals,
  Page,
  Payment,
  Project,
  ProjectListItem,
} from "@/types/api";

const PAGE_SIZE = 10;

export function PaymentsTab({
  project,
  refreshToken,
  onProjectChanged,
  onNewPayment,
}: {
  project: Project;
  refreshToken: number;
  onProjectChanged: () => void;
  onNewPayment: () => void;
}) {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editTarget, setEditTarget] = useState<Payment | null>(null);

  const payments = useApiData<Page<Payment>>(
    (signal) =>
      api.get<Page<Payment>>(
        `/projects/${project.id}/payments${queryString({
          status,
          page,
          page_size: PAGE_SIZE,
        })}`,
        signal,
      ),
    [project.id, status, page, refreshToken],
  );

  const accounting = useApiData<{ totals: CurrencyTotals[] }>(
    (signal) =>
      api.get<{ totals: CurrencyTotals[] }>(
        `/accounting/projects/${project.id}/totals`,
        signal,
      ),
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

  return (
    <div className="space-y-4">
      {(accounting.data?.totals.length ?? 0) > 0 && (
        <div className="panel p-4">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-xs font-semibold">مانده حساب</h3>
            <Link
              href="/accounting?tab=receipts"
              className="text-[11px] text-accent hover:underline"
            >
              بررسی رسیدها و تخصیص
            </Link>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {accounting.data?.totals.map((total) => (
              <div
                key={total.currency}
                className="rounded-xl border border-line/60 bg-black/10 p-2.5 text-[11px]"
              >
                <div className="mb-1 flex items-center justify-between text-muted">
                  <span>{total.currency}</span>
                  <span className={total.settled ? "text-success" : "text-warning"}>
                    {total.settled ? "تسویه" : "بدهی باز"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">بدهی</span>
                  <span>{formatAmount(total.debt_minor, total.currency as Currency)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">مانده</span>
                  <span className={total.balance_minor ? "text-warning" : "text-success"}>
                    {formatAmount(total.balance_minor, total.currency as Currency)}
                  </span>
                </div>
                {total.credit_minor > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted">اعتبار</span>
                    <span>
                      {formatAmount(total.credit_minor, total.currency as Currency)}
                    </span>
                  </div>
                )}
                {total.pending_receipts > 0 && (
                  <div className="mt-1 text-warning">
                    {total.pending_receipts} رسید در انتظار بررسی
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-2">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            className="field-input sm:w-52"
            aria-label="فیلتر وضعیت پرداخت"
          >
            <option value="">همه وضعیت ها</option>
            {Object.entries(PAYMENT_STATUS).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
        </div>
        <Button size="sm" onClick={onNewPayment}>
          <Plus size={14} aria-hidden />
          ثبت پرداخت
        </Button>
      </div>

      <div className="panel overflow-hidden">
        {payments.error && !payments.data ? (
          <ErrorState message={payments.error} onRetry={payments.reload} />
        ) : payments.loading && !payments.data ? (
          <SkeletonRows rows={4} />
        ) : payments.data && payments.data.items.length === 0 ? (
          <EmptyState
            icon={<Wallet size={22} aria-hidden />}
            title={status ? "پرداختی با این وضعیت وجود ندارد" : "پرداختی ثبت نشده است"}
            description={
              status
                ? "فیلتر وضعیت را تغییر دهید."
                : "وضعیت مالی پروژه را ثبت کنید تا یادآوری سررسید به صورت خودکار زمان بندی شود."
            }
            action={
              status ? (
                <Button variant="secondary" onClick={() => setStatus("")}>
                  نمایش همه
                </Button>
              ) : (
                <Button onClick={onNewPayment}>
                  <Plus size={15} aria-hidden />
                  ثبت پرداخت
                </Button>
              )
            }
          />
        ) : payments.data ? (
          <>
            <div className="overflow-x-auto">
              <table className="data-table min-w-[760px]">
                <thead>
                  <tr>
                    <th>عنوان</th>
                    <th>مبلغ</th>
                    <th>سررسید</th>
                    <th>وضعیت</th>
                    <th>یادآوری بعدی</th>
                    <th>یادداشت</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {payments.data.items.map((payment) => (
                    <tr key={payment.id}>
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
                      <td className="max-w-40 text-[10px] text-muted">
                        <span className="line-clamp-2">{payment.notes || "—"}</span>
                      </td>
                      <td>
                        <PaymentActions
                          payment={payment}
                          onEdit={() => setEditTarget(payment)}
                          onChanged={() => {
                            payments.reload();
                            onProjectChanged();
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={payments.data} onChange={setPage} label="پرداخت" />
          </>
        ) : null}
      </div>

      <div className="panel p-4 text-[10px] leading-6 text-muted">
        وضعیت مالی و وضعیت ارسال پیام دو مفهوم جدا هستند. یادآوری پرداخت فقط برای پرداخت
        تسویه نشده و در زمان زمان بندی شده ارسال می شود. تراکنش بانکی توسط این سیستم تایید
        نمی شود.
      </div>

      {editTarget ? (
        <PaymentFormModal
          open
          onClose={() => setEditTarget(null)}
          projects={projectAsList}
          fixedProjectId={project.id}
          payment={editTarget}
          onSaved={() => {
            payments.reload();
            onProjectChanged();
          }}
        />
      ) : null}
    </div>
  );
}
