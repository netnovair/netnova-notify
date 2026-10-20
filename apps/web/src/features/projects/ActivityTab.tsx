"use client";

import { useState } from "react";

import { Pagination } from "@/components/ui/Pagination";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { AuditTimeline } from "@/features/audit/AuditTimeline";
import { api, queryString } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import type { AuditLog, Page, Project } from "@/types/api";

const PAGE_SIZE = 15;

export function ActivityTab({
  project,
  refreshToken,
}: {
  project: Project;
  refreshToken: number;
}) {
  const [page, setPage] = useState(1);
  const logs = useApiData<Page<AuditLog>>(
    (signal) =>
      api.get<Page<AuditLog>>(
        `/projects/${project.id}/audit-logs${queryString({ page, page_size: PAGE_SIZE })}`,
        signal,
      ),
    [project.id, page, refreshToken],
  );

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
        <h2 className="text-sm font-semibold">تاریخچه فعالیت پروژه</h2>
        <p className="text-[10px] text-muted">ثبت خودکار عملیات حساس</p>
      </div>
      {logs.error && !logs.data ? (
        <ErrorState message={logs.error} onRetry={logs.reload} />
      ) : logs.loading && !logs.data ? (
        <SkeletonRows rows={4} />
      ) : logs.data ? (
        <>
          <div className="p-4">
            <AuditTimeline logs={logs.data.items} />
          </div>
          <Pagination page={logs.data} onChange={setPage} label="رویداد" />
        </>
      ) : null}
    </div>
  );
}
