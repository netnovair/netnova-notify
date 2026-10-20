"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { NotificationStatusBadge } from "@/components/ui/StatusBadge";
import { NotificationActions } from "@/features/notifications/NotificationActions";
import { formatDateTime } from "@/lib/format";
import { NOTIFICATION_TYPE } from "@/lib/labels";
import { useApiData } from "@/lib/hooks";
import { api } from "@/lib/api";
import type { Notification } from "@/types/api";

export function NotificationDetailModal({
  notificationId,
  onClose,
  onChanged,
}: {
  notificationId: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { data, error, loading, reload } = useApiData<Notification>(
    (signal) => api.get<Notification>(`/notifications/${notificationId}`, signal),
    [notificationId],
  );

  useEffect(() => {
    if (!notificationId) return;
    const timer = window.setInterval(reload, 8000);
    return () => window.clearInterval(timer);
  }, [notificationId, reload]);

  return (
    <Modal
      open={Boolean(notificationId)}
      onClose={onClose}
      title="جزئیات اطلاعیه"
      description={data ? `شناسه: ${data.id}` : undefined}
      size="lg"
    >
      {!notificationId ? null : loading && !data ? (
        <LoadingState compact />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={reload} compact />
      ) : data ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <NotificationStatusBadge status={data.status} />
            <Badge tone="accent">{NOTIFICATION_TYPE[data.type]}</Badge>
            {data.deliveries.some((delivery) => delivery.is_mock) ? (
              <Badge tone="info">شبیه سازی شده</Badge>
            ) : null}
            <span className="text-xs text-muted">
              {data.attempt_count} تلاش ثبت شده
            </span>
          </div>

          <div className="rounded-xl border border-line bg-elevated/50 p-4">
            <h3 className="text-sm font-semibold text-ink">{data.title}</h3>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-8 text-muted">{data.body}</p>
          </div>

          {data.last_error ? (
            <div className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/[0.06] px-4 py-3 text-xs leading-7 text-[#ffb4b4]">
              <AlertTriangle size={15} className="mt-1 shrink-0" aria-hidden />
              <div>
                <p className="font-medium">آخرین خطا</p>
                <p className="mt-0.5 break-words">{data.last_error}</p>
              </div>
            </div>
          ) : null}

          <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
            <div className="flex justify-between gap-3 border-b border-line-soft py-2">
              <dt className="text-muted">ثبت</dt>
              <dd>{formatDateTime(data.created_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line-soft py-2">
              <dt className="text-muted">زمان بندی</dt>
              <dd>{formatDateTime(data.scheduled_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line-soft py-2">
              <dt className="text-muted">ارسال</dt>
              <dd>{formatDateTime(data.sent_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-line-soft py-2">
              <dt className="text-muted">شناسه پیام تلگرام</dt>
              <dd dir="ltr">{data.telegram_message_id ?? "—"}</dd>
            </div>
          </dl>

          <div>
            <h3 className="mb-2 text-sm font-semibold">تلاش های ارسال</h3>
            {data.deliveries.length === 0 ? (
              <p className="rounded-xl border border-line-soft bg-elevated/40 px-4 py-3 text-xs text-muted">
                هنوز تلاشی برای ارسال این اطلاعیه ثبت نشده است.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="data-table min-w-[560px]">
                  <thead>
                    <tr>
                      <th>تلاش</th>
                      <th>مقصد (شناسه تلگرام)</th>
                      <th>وضعیت</th>
                      <th>شناسه پیام</th>
                      <th>زمان پایان</th>
                      <th>خطا</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.deliveries.map((delivery) => (
                      <tr key={delivery.id}>
                        <td>{delivery.attempt_no}</td>
                        <td dir="ltr" className="text-start text-xs">
                          {delivery.chat_id}
                        </td>
                        <td>
                          <div className="flex flex-wrap items-center gap-1">
                            <Badge
                              tone={
                                delivery.status === "sent"
                                  ? "success"
                                  : delivery.status === "failed"
                                    ? "danger"
                                    : delivery.status === "unknown"
                                      ? "warning"
                                      : "info"
                              }
                            >
                              {delivery.status === "sent"
                                ? "ارسال شده"
                                : delivery.status === "failed"
                                  ? "ناموفق"
                                  : delivery.status === "unknown"
                                    ? "نامشخص"
                                    : "در جریان"}
                            </Badge>
                            {delivery.is_mock ? <Badge tone="info">Mock</Badge> : null}
                          </div>
                        </td>
                        <td dir="ltr" className="text-start text-xs">
                          {delivery.telegram_message_id ?? "—"}
                        </td>
                        <td className="text-xs text-muted">{formatDateTime(delivery.finished_at)}</td>
                        <td className="max-w-56 text-xs text-[#ffb4b4]">
                          {delivery.error ? (
                            <span className="line-clamp-2 break-words">{delivery.error}</span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-[11px] text-muted">
              جزئیات ارسال از داده واقعی پایگاه داده خوانده می شود.
            </p>
            <NotificationActions
              notification={data}
              onChanged={() => {
                reload();
                onChanged();
              }}
            />
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
