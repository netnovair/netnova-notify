"use client";

import { BellRing, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
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
  Project,
} from "@/types/api";

const ACTIVE_STATUSES: NotificationStatus[] = ["queued", "sending", "retry_wait"];
const PAGE_SIZE = 10;

export function NotificationsTab({
  project,
  refreshToken,
  onProjectChanged,
  onNewNotification,
}: {
  project: Project;
  refreshToken: number;
  onProjectChanged: () => void;
  onNewNotification: () => void;
}) {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);

  const notifications = useApiData<Page<NotificationListItem>>(
    (signal) =>
      api.get<Page<NotificationListItem>>(
        `/projects/${project.id}/notifications${queryString({
          status,
          page,
          page_size: PAGE_SIZE,
        })}`,
        signal,
      ),
    [project.id, status, page, refreshToken],
  );

  const hasActive = (notifications.data?.items ?? []).some((item) =>
    ACTIVE_STATUSES.includes(item.status),
  );
  useAutoRefresh(notifications.reload, 10_000, hasActive);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 items-center gap-2">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            className="field-input sm:w-52"
            aria-label="فیلتر وضعیت اطلاعیه"
          >
            <option value="">همه وضعیت ها</option>
            {Object.entries(NOTIFICATION_STATUS).map(([key, value]) => (
              <option key={key} value={key}>
                {value.label}
              </option>
            ))}
          </select>
          <Button variant="ghost" size="sm" onClick={notifications.reload}>
            <RefreshCw size={14} aria-hidden />
            به روزرسانی
          </Button>
          {hasActive ? (
            <span className="hidden text-[10px] text-muted sm:inline" aria-live="polite">
              به روزرسانی خودکار هر ۱۰ ثانیه
            </span>
          ) : null}
        </div>
        <Button size="sm" onClick={onNewNotification}>
          <Plus size={14} aria-hidden />
          اطلاعیه جدید
        </Button>
      </div>

      <div className="panel overflow-hidden">
        {notifications.error && !notifications.data ? (
          <ErrorState message={notifications.error} onRetry={notifications.reload} />
        ) : notifications.loading && !notifications.data ? (
          <SkeletonRows rows={5} />
        ) : notifications.data && notifications.data.items.length === 0 ? (
          <EmptyState
            icon={<BellRing size={22} aria-hidden />}
            title={status ? "اطلاعیه ای با این وضعیت وجود ندارد" : "هنوز اطلاعیه ای ثبت نشده است"}
            description={
              status
                ? "فیلتر وضعیت را تغییر دهید یا همه اطلاعیه ها را ببینید."
                : "اولین اطلاعیه این پروژه را ثبت کنید تا برای کارفرمای متصل ارسال شود."
            }
            action={
              status ? (
                <Button variant="secondary" onClick={() => setStatus("")}>
                  نمایش همه
                </Button>
              ) : (
                <Button onClick={onNewNotification}>
                  <Plus size={15} aria-hidden />
                  ثبت اطلاعیه
                </Button>
              )
            }
          />
        ) : notifications.data ? (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>عنوان</th>
                    <th>نوع</th>
                    <th>وضعیت</th>
                    <th>زمان بندی / ارسال</th>
                    <th>تلاش</th>
                    <th>خطای آخر</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {notifications.data.items.map((item) => (
                    <tr key={item.id}>
                      <td className="max-w-56">
                        <button
                          type="button"
                          onClick={() => setDetailId(item.id)}
                          className="text-start font-medium text-ink hover:text-[#c6b8ff]"
                        >
                          {item.title}
                        </button>
                        <p className="mt-0.5 text-[10px] text-muted">
                          ثبت: {formatDateTime(item.created_at)}
                        </p>
                      </td>
                      <td className="text-xs">
                        <div className="flex flex-wrap items-center gap-1">
                          <span>{NOTIFICATION_TYPE[item.type]}</span>
                          {item.is_mock ? <Badge tone="info">Mock</Badge> : null}
                        </div>
                      </td>
                      <td>
                        <NotificationStatusBadge status={item.status} />
                      </td>
                      <td className="text-xs text-muted">
                        {item.status === "sent"
                          ? formatDateTime(item.sent_at)
                          : item.scheduled_at
                            ? `زمان بندی: ${formatDateTime(item.scheduled_at)}`
                            : "—"}
                      </td>
                      <td className="text-xs">{item.attempt_count}</td>
                      <td className="max-w-48 text-[10px] text-[#ffb4b4]">
                        {item.last_error ? (
                          <span className="line-clamp-2" title={item.last_error}>
                            {item.last_error}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td>
                        <NotificationActions
                          notification={item}
                          compact
                          onChanged={() => {
                            notifications.reload();
                            onProjectChanged();
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-line-soft md:hidden">
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
                    {NOTIFICATION_TYPE[item.type]} · ثبت {formatDateTime(item.created_at)}
                    {item.scheduled_at ? ` · زمان بندی ${formatDateTime(item.scheduled_at)}` : ""}
                  </p>
                  {item.last_error ? (
                    <p className="mt-2 line-clamp-2 text-[10px] leading-6 text-[#ffb4b4]">
                      {item.last_error}
                    </p>
                  ) : null}
                  <div className="mt-3">
                    <NotificationActions
                      notification={item}
                      compact
                      onChanged={() => {
                        notifications.reload();
                        onProjectChanged();
                      }}
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
        onChanged={() => {
          notifications.reload();
          onProjectChanged();
        }}
      />
    </div>
  );
}
