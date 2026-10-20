"use client";

import Link from "next/link";
import { useState } from "react";

import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { api } from "@/lib/api";
import { formatAmount } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { AccountingOverview, Currency } from "@/types/api";

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warning" | "success";
}) {
  return (
    <div className="rounded-xl border border-line/60 bg-black/10 p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div
        className={
          tone === "warning"
            ? "mt-1 text-sm font-semibold text-warning"
            : tone === "success"
              ? "mt-1 text-sm font-semibold text-success"
              : "mt-1 text-sm font-semibold text-ink"
        }
      >
        {value}
      </div>
    </div>
  );
}

export function OverviewPanel({ refreshKey }: { refreshKey: number }) {
  const [selected, setSelected] = useState<string>("");

  const overview = useApiData<AccountingOverview>(
    (signal) => api.get<AccountingOverview>("/accounting/overview", signal),
    [refreshKey],
  );
  const scoped = useApiData<AccountingOverview>(
    (signal) =>
      selected
        ? api.get<AccountingOverview>(`/accounting/projects/${selected}/totals`, signal)
        : Promise.resolve({ totals: [], projects: [] }),
    [selected, refreshKey],
  );

  if (overview.loading) return <SkeletonRows rows={4} />;
  if (overview.error) return <ErrorState message={overview.error} onRetry={overview.reload} />;

  const data = overview.data ?? { totals: [], projects: [] };
  const rows = selected ? (scoped.data?.projects ?? data.projects) : data.projects;
  const activeProject = data.projects.find((row) => row.project_id === selected);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.totals.length === 0 && (
          <div className="panel col-span-full p-4 text-sm text-muted">
            هنوز فاکتوری ثبت نشده است.
          </div>
        )}
        {data.totals.map((total) => (
          <div key={total.currency} className="panel space-y-3 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted">جمع کل ({total.currency})</span>
              <span
                className={
                  total.settled
                    ? "badge badge-success"
                    : total.pending_receipts
                      ? "badge badge-warning"
                      : "badge"
                }
              >
                {total.settled ? "تسویه" : "بدهی باز"}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Metric
                label="بدهی"
                value={formatAmount(total.debt_minor, total.currency as Currency)}
              />
              <Metric
                label="مانده حساب"
                value={formatAmount(total.balance_minor, total.currency as Currency)}
                tone={total.balance_minor > 0 ? "warning" : "success"}
              />
              <Metric
                label="پرداخت شده"
                value={formatAmount(total.paid_minor, total.currency as Currency)}
              />
              <Metric
                label="اعتبار"
                value={formatAmount(total.credit_minor, total.currency as Currency)}
              />
            </div>
            {total.overdue_minor > 0 && (
              <p className="text-[11px] text-danger">
                سررسید گذشته: {formatAmount(total.overdue_minor, total.currency as Currency)}
              </p>
            )}
            <p className="text-[11px] text-muted">
              {total.pending_receipts > 0
                ? `${total.pending_receipts} رسید در انتظار بررسی`
                : "رسید بررسی نشده ای نیست"}
            </p>
          </div>
        ))}
      </div>

      <div className="panel p-4">
        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-semibold">مانده حساب پروژه ها</h2>
          <select
            className="field-input sm:w-64"
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
            aria-label="انتخاب پروژه"
          >
            <option value="">همه پروژه ها</option>
            {data.projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.project_name}
              </option>
            ))}
          </select>
        </div>

        {rows.length === 0 ? (
          <EmptyState
            title="اطلاعات مالی ثبت نشده است"
            description="با ثبت فاکتور در بخش پرداخت ها، بدهی و مانده حساب هر پروژه اینجا محاسبه می شود."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="text-muted">
                <tr className="border-b border-line/60">
                  <th className="py-2 font-normal">پروژه</th>
                  <th className="py-2 font-normal">بدهی</th>
                  <th className="py-2 font-normal">پرداخت شده</th>
                  <th className="py-2 font-normal">اعتبار</th>
                  <th className="py-2 font-normal">مانده حساب</th>
                  <th className="py-2 font-normal">رسید باز</th>
                  <th className="py-2 font-normal" />
                </tr>
              </thead>
              <tbody>
                {(selected && activeProject ? [activeProject] : rows).flatMap((project) =>
                  project.totals.length === 0
                    ? [
                        <tr key={`${project.project_id}-empty`} className="border-b border-line/30">
                          <td className="py-3">{project.project_name}</td>
                          <td className="py-3 text-muted" colSpan={6}>
                            فاکتوری ثبت نشده است.
                          </td>
                        </tr>,
                      ]
                    : project.totals.map((total) => (
                        <tr
                          key={`${project.project_id}-${total.currency}`}
                          className="border-b border-line/30"
                        >
                          <td className="py-3">
                            <Link
                              href={`/projects/${project.project_id}`}
                              className="hover:text-accent"
                            >
                              {project.project_name}
                            </Link>
                          </td>
                          <td className="py-3">
                            {formatAmount(total.debt_minor, total.currency as Currency)}
                          </td>
                          <td className="py-3">
                            {formatAmount(total.paid_minor, total.currency as Currency)}
                          </td>
                          <td className="py-3">
                            {formatAmount(total.credit_minor, total.currency as Currency)}
                          </td>
                          <td
                            className={
                              total.balance_minor > 0 ? "py-3 text-warning" : "py-3 text-success"
                            }
                          >
                            {total.settled
                              ? "تسویه"
                              : formatAmount(total.balance_minor, total.currency as Currency)}
                          </td>
                          <td className="py-3">
                            {total.pending_receipts > 0 ? total.pending_receipts : "—"}
                          </td>
                          <td className="py-3">
                            <Link
                              href={`/payments?project_id=${project.project_id}`}
                              className="text-accent hover:underline"
                            >
                              فاکتورها
                            </Link>
                          </td>
                        </tr>
                      )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
