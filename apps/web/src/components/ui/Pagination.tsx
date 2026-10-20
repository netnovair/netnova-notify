"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { formatNumber } from "@/lib/format";
import type { Page } from "@/types/api";

export function Pagination({
  page,
  onChange,
  label = "مورد",
}: {
  page: Pick<Page<unknown>, "page" | "pages" | "total">;
  onChange: (page: number) => void;
  label?: string;
}) {
  if (page.total === 0) return null;
  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-line px-4 py-3 text-xs text-muted sm:flex-row">
      <p>
        {formatNumber(page.total)} {label} · صفحه {formatNumber(page.page)} از{" "}
        {formatNumber(Math.max(page.pages, 1))}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(page.page - 1)}
          disabled={page.page <= 1}
          className="inline-flex h-9 items-center gap-1 rounded-lg border border-line px-3 transition hover:border-accent/50 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronRight size={14} aria-hidden />
          قبلی
        </button>
        <button
          type="button"
          onClick={() => onChange(page.page + 1)}
          disabled={page.page >= page.pages}
          className="inline-flex h-9 items-center gap-1 rounded-lg border border-line px-3 transition hover:border-accent/50 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
        >
          بعدی
          <ChevronLeft size={14} aria-hidden />
        </button>
      </div>
    </div>
  );
}
