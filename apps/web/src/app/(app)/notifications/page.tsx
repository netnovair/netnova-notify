"use client";

import { BellRing, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { NotificationStatusBadge } from "@/components/ui/StatusBadge";
import { NotificationActions } from "@/features/notifications/NotificationActions";
import { NotificationDetailModal } from "@/features/notifications/NotificationDetailModal";
import { api, queryString } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { NOTIFICATION_STATUS, NOTIFICATION_TYPE } from "@/lib/labels";
import { useApiData, useAutoRefresh } from "@/lib/hooks";
import type {
  NotificationListItem,
  NotificationStatus,
  Page,
  ProjectListItem,
} from "@/types/api";

const PAGE_SIZE = 20;
const ACTIVE_STATUSES: NotificationStatus[] = ["queued", "sending", "retry_wait"];

function NotificationsContent() {
  const params = useSearchParams();
  const initialStatus = params.get("status") ?? "";
  const [status, setStatus] = useState(initialStatus);
  const [projectId, setProjectId] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);

  const notifications = useApiData<Page<NotificationListItem>>(
    (signal) =>
      api.get<Page<NotificationListItem>>(
        `/notifications${queryString({
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

  const hasActive = (notifications.data?.items ?? []).some((item) =>
    ACTIVE_STATUSES.includes(item.status),
  );
  useAutoRefresh(notifications.reload, 10_000, hasActive);

  return (
    <>
      <PageHeader
        eyebrow="مدیریت"
        title="تاریخچه ارسال"
        subtitle="وضعیت هر اطلاعیه، تلاش های ارسال و خطاهای ثبت شده از پایگاه داده خوانده می شود."
        actions={
          <Button variant="secondary" size="sm" onClick={notifications.reload}>
            <RefreshCw size={14} aria-hidden />
            به روزرسانی
          </Button>
        }
      />

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
          {(projects.data?.items ?? []).map((project) => (
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
          aria-label="فیلتر وضعیت"
        >
          <option value="">همه وضعیت ها</option>
          {Object.entries(NOTIFICATION_STATUS).map(([key, value]) => (
            <option key={key} value={key}>
              {value.label}
            </option>
          ))}
        </select>
        {hasActive ? (
          <span className="self-center text-[10px] text-muted" aria-live="polite">
            به روزرسانی خودکار هر ۱۰ ثانیه فعال است.
          </span>
        ) : null}
      </div>

      <div className="panel overflow-hidden">
        {notifications.error && !notifications.data ? (
          <ErrorState message={notifications.error} onRetry={notifications.reload} />
        ) : notifications.loading && !notifications.data ? (
          <SkeletonRows rows={7} />
        ) : notifications.data && notifications.data.items.length === 0 ? (
          <EmptyState
            icon={<BellRing size={24} aria-hidden />}
            title="اطلاعیه ای مطابق فیلتر یافت نشد"
            description="اطلاعیه ها از صفحه هر پروژه ثبت می شوند. پس از ثبت، وضعیت ارسال در همین صفحه قابل پیگیری است."
            action={
              status || projectId ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setStatus("");
                    setProjectId("");
                    setPage(1);
                  }}
                >
                  پاک کردن فیلترها
                </Button>
              ) : (
                <Link href="/projects">
                  <Button>رفتن به پروژه ها</Button>
                </Link>
              )
            }
          />
        ) : notifications.data ? (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>پروژه</th>
                    <th>عنوان</th>
                    <th>نوع</th>
                    <th>وضعیت</th>
                    <th>ثبت</th>
                    <th>ارسال / زمان بندی</th>
                    <th>تلاش</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {notifications.data.items.map((item) => (
                    <tr key={item.id}>
                      <td className="text-xs text-muted">{item.project_name ?? "—"}</td>
                      <td className="max-w-56">
                        <button
                          type="button"
                          onClick={() => setDetailId(item.id)}
                          className="text-start text-sm text-ink hover:text-[#c6b8ff]"
                        >
                          {item.title}
                        </button>
                        {item.last_error ? (
                          <p className="mt-0.5 line-clamp-1 text-[10px] text-[#ffb4b4]">
                            {item.last_error}
                          </p>
                        ) : null}
                      </td>
                      <td className="text-xs">
                        <div className="flex flex-wrap items-center gap-1">
                          {NOTIFICATION_TYPE[item.type]}
                          {item.is_mock ? <Badge tone="info">Mock</Badge> : null}
                        </div>
                      </td>
                      <td>
                        <NotificationStatusBadge status={item.status} />
                      </td>
                      <td className="text-xs text-muted">{formatDateTime(item.created_at)}</td>
                      <td className="text-xs text-muted">
                        {item.status === "sent"
                          ? formatDateTime(item.sent_at)
                          : item.scheduled_at
                            ? formatDateTime(item.scheduled_at)
                            : "—"}
                      </td>
                      <td className="text-xs">{item.attempt_count}</td>
                      <td>
                        <NotificationActions
                          notification={item}
                          compact
                          onChanged={notifications.reload}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-line-soft lg:hidden">
              {notifications.data.items.map((item) => (
                <li key={item.id} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setDetailId(item.id)}
                      className="text-start text-sm font-medium text-ink"
                    >
                      {item.title}
                    </button>
                    <NotificationStatusBadge status={item.status} />
                  </div>
                  <p className="mt-1 text-[10px] text-muted">
                    {item.project_name ?? "—"} · {NOTIFICATION_TYPE[item.type]} ·{" "}
                    {formatDateTime(item.created_at)}
                  </p>
                  {item.last_error ? (
                    <p className="mt-1.5 line-clamp-2 text-[10px] leading-6 text-[#ffb4b4]">
                      {item.last_error}
                    </p>
                  ) : null}
                  <div className="mt-3">
                    <NotificationActions
                      notification={item}
                      compact
                      onChanged={notifications.reload}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <Pagination page={notifications.data} onChange={setPage} label="اطلاعیه" />
          </>
        ) : null}
      </div>

      <NotificationDetailModal
        notificationId={detailId}
        onClose={() => setDetailId(null)}
        onChanged={notifications.reload}
      />
    </>
  );
}

export default function NotificationsPage() {
  return (
    <Suspense fallback={<div className="panel mt-10"><SkeletonRows rows={6} /></div>}>
      <NotificationsContent />
    </Suspense>
  );
}
