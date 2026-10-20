"use client";

import Link from "next/link";

import { SkeletonRows } from "@/components/ui/States";
import { api } from "@/lib/api";
import { formatAmount } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { AccountingOverview, Currency } from "@/types/api";

/**
 * The home page shows the same numbers as the accounting page: debt and the
 * remaining balance per currency, plus the projects with an open balance.
 * When nothing is recorded the block says so instead of showing zeros.
 */
export function HomeAccountingSummary() {
  const overview = useApiData<AccountingOverview>(
    (signal) => api.get<AccountingOverview>("/accounting/overview", signal),
    [],
  );

  if (overview.loading) return <SkeletonRows rows={2} />;
  if (overview.error || !overview.data) return null;

  const totals = overview.data.totals.filter(
    (total) => total.invoices_total > 0 || total.credit_minor > 0,
  );
  if (totals.length === 0) {
    return (
      <section className="panel mt-4 p-5" aria-labelledby="accounting-title">
        <div className="mb-2 flex items-center justify-between">
          <h2 id="accounting-title" className="text-sm font-semibold">
            وضعیت مالی
          </h2>
          <Link href="/accounting" className="text-[11px] text-accent hover:underline">
            حسابداری
          </Link>
        </div>
        <p className="text-xs text-muted">
          هنوز فاکتوری ثبت نشده است. با ثبت پرداخت در بخش پرداخت ها، بدهی و مانده حساب اینجا
          محاسبه می شود.
        </p>
      </section>
    );
  }

  const withBalance = overview.data.projects
    .flatMap((project) =>
      project.totals.map((total) => ({ project, total })),
    )
    .filter((row) => row.total.balance_minor > 0)
    .sort((a, b) => b.total.balance_minor - a.total.balance_minor)
    .slice(0, 4);

  const pending = totals.reduce((sum, total) => sum + total.pending_receipts, 0);

  return (
    <section className="panel mt-4 p-5" aria-labelledby="accounting-title">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="accounting-title" className="text-sm font-semibold">
          وضعیت مالی
        </h2>
        <div className="flex items-center gap-3 text-[11px]">
          {pending > 0 && (
            <Link href="/accounting?tab=receipts" className="text-warning hover:underline">
              {pending} رسید در انتظار بررسی
            </Link>
          )}
          <Link href="/accounting" className="text-accent hover:underline">
            حسابداری
          </Link>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {totals.map((total) => (
          <div key={total.currency} className="rounded-xl border border-line/60 p-3">
            <div className="flex items-center justify-between text-[11px] text-muted">
              <span>{total.currency}</span>
              <span className={total.settled ? "text-success" : "text-warning"}>
                {total.settled ? "تسویه" : "بدهی باز"}
              </span>
            </div>
            <div className="mt-2 space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-muted">بدهی</span>
                <span>{formatAmount(total.debt_minor, total.currency as Currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">مانده حساب</span>
                <span
                  className={total.balance_minor > 0 ? "text-warning" : "text-success"}
                >
                  {formatAmount(total.balance_minor, total.currency as Currency)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {withBalance.length > 0 && (
        <ul className="mt-3 divide-y divide-line/40 text-xs">
          {withBalance.map(({ project, total }) => (
            <li
              key={`${project.project_id}-${total.currency}`}
              className="flex items-center justify-between gap-2 py-2"
            >
              <Link href={`/projects/${project.project_id}`} className="hover:text-accent">
                {project.project_name}
              </Link>
              <span className="text-muted">
                {formatAmount(total.balance_minor, total.currency as Currency)}
                {total.overdue_minor > 0 && (
                  <span className="mr-2 text-danger">
                    (سررسید گذشته:{" "}
                    {formatAmount(total.overdue_minor, total.currency as Currency)})
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
