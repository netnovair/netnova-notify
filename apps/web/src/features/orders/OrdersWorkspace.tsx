"use client";

import clsx from "clsx";
import { ClipboardList, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, queryString } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import { ORDER_STATUS } from "@/lib/labels";
import type { Order, OrderCounters, OrderListItem, OrderStatus, Page } from "@/types/api";

const STATUS_FILTERS: Array<{ value: OrderStatus | ""; label: string }> = [
  { value: "", label: "همه" },
  { value: "new", label: "جدید" },
  { value: "contacted", label: "تماس گرفته شد" },
  { value: "quoted", label: "پیشنهاد ارسال شد" },
  { value: "won", label: "تبدیل به مشتری" },
  { value: "lost", label: "منصرف شد" },
  { value: "cancelled", label: "لغو شده" },
];

const STATUS_ORDER: Array<OrderStatus | "total"> = [
  "new",
  "contacted",
  "quoted",
  "won",
  "lost",
  "cancelled",
  "total",
];

function StatusBadge({ status }: { status: OrderStatus }) {
  const spec = ORDER_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

function OrderDetailModal({
  orderId,
  onClose,
  onChanged,
}: {
  orderId: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const order = useApiData<Order>(
    (signal) => api.get<Order>(`/orders/${orderId}`, signal),
    [orderId],
  );
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const data = order.data;
  const noteValue = note === "" ? (data?.admin_note ?? "") : note;

  async function patch(payload: { status?: OrderStatus; admin_note?: string }) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await api.patch<Order>(`/orders/${data.id}`, payload);
      notify("سفارش به روز شد.", "success");
      order.reload();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={orderId !== null}
      onClose={onClose}
      title={data ? `سفارش ${data.item_title}` : "جزئیات سفارش"}
      description="پاسخ های کارفرما دقیقا همان چیزی است که در ربات ثبت شده است."
      size="lg"
      footer={
        <Button variant="secondary" onClick={onClose}>
          بستن
        </Button>
      }
    >
      {order.error && !data ? (
        <ErrorState message={order.error} onRetry={order.reload} compact />
      ) : order.loading && !data ? (
        <SkeletonRows rows={5} />
      ) : data ? (
        <div className="space-y-4">
          {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">خدمت</p>
              <p className="mt-1 text-xs font-medium">
                {data.category_title} · {data.item_title}
              </p>
            </div>
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">ثبت شده در</p>
              <p className="mt-1 text-xs">{formatDateTime(data.created_at)}</p>
            </div>
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">نام و نام خانوادگی</p>
              <p className="mt-1 text-xs">{data.contact_name}</p>
            </div>
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">شماره تماس</p>
              <p className="mt-1 text-xs" dir="ltr">
                {data.contact_phone}
              </p>
            </div>
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">تلگرام</p>
              <p className="mt-1 text-xs" dir="ltr">
                {data.telegram_username ? `@${data.telegram_username}` : data.telegram_id}
              </p>
            </div>
            <div className="rounded-xl border border-line-soft p-3">
              <p className="text-[10px] text-muted">وضعیت</p>
              <p className="mt-1">
                <StatusBadge status={data.status} />
              </p>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold">پاسخ های کارفرما</h3>
            {data.answers.length === 0 ? (
              <p className="text-[11px] text-muted">پاسخی ثبت نشده است.</p>
            ) : (
              <ul className="divide-y divide-line-soft rounded-xl border border-line-soft">
                {data.answers.map((answer) => (
                  <li
                    key={answer.key}
                    className="grid gap-1 px-3 py-2 text-[11px] sm:grid-cols-[180px_1fr]"
                  >
                    <span className="text-muted">{answer.label}</span>
                    <span className="leading-6">{answer.value}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold">تغییر وضعیت</h3>
            <div className="flex flex-wrap gap-1.5">
              {STATUS_FILTERS.filter((filter) => filter.value !== "").map((filter) => (
                <Button
                  key={filter.value}
                  size="sm"
                  variant={data.status === filter.value ? "primary" : "secondary"}
                  disabled={busy}
                  onClick={() => void patch({ status: filter.value as OrderStatus })}
                >
                  {filter.label}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="order-note" className="field-label">
              یادداشت داخلی
            </label>
            <textarea
              id="order-note"
              className="field-input min-h-20 resize-y"
              value={noteValue}
              onChange={(event) => setNote(event.target.value)}
              placeholder="این یادداشت فقط در پنل دیده می شود."
            />
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                onClick={() => void patch({ admin_note: noteValue })}
                loading={busy}
              >
                ذخیره یادداشت
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

export function OrdersWorkspace() {
  const [status, setStatus] = useState<OrderStatus | "">("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);

  const counters = useApiData<OrderCounters>(
    (signal) => api.get<OrderCounters>("/orders/counters", signal),
    [],
  );
  const orders = useApiData<Page<OrderListItem>>(
    (signal) =>
      api.get<Page<OrderListItem>>(
        `/orders${queryString({ status, search: query, page, page_size: 20 })}`,
        signal,
      ),
    [status, query, page],
  );

  function reloadAll() {
    counters.reload();
    orders.reload();
  }

  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <ClipboardList size={18} className="text-[#b9a7ff]" aria-hidden />
          <h2 className="text-sm font-semibold">سفارش های ثبت سفارش</h2>
          <Button size="sm" variant="ghost" className="ms-auto" onClick={reloadAll}>
            <RefreshCw size={13} aria-hidden /> به روزرسانی
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {STATUS_ORDER.map((key) => {
            const label = key === "total" ? "همه" : ORDER_STATUS[key].label;
            const value = counters.data?.[key] ?? 0;
            const active = key === "total" ? status === "" : status === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setStatus(key === "total" ? "" : key);
                  setPage(1);
                }}
                className={clsx(
                  "rounded-xl border px-3 py-2 text-start transition",
                  active
                    ? "border-accent/60 bg-accent/10"
                    : "border-line-soft bg-white/[0.02] hover:border-accent/40",
                )}
              >
                <span className="block text-[10px] text-muted">{label}</span>
                <span className="mt-0.5 block text-sm font-semibold">
                  {counters.loading && !counters.data ? "…" : value}
                </span>
              </button>
            );
          })}
        </div>
        <form
          className="mt-3 flex flex-wrap gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setQuery(search.trim());
          }}
        >
          <div className="relative min-w-0 flex-1">
            <Search
              size={14}
              aria-hidden
              className="pointer-events-none absolute inset-y-0 start-3 my-auto text-muted"
            />
            <input
              className="field-input ps-9"
              placeholder="جستجو بر اساس نام، شماره تماس یا خدمت"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="جستجوی سفارش"
            />
          </div>
          <Button type="submit" variant="secondary">
            جستجو
          </Button>
          {query ? (
            <Button
              variant="ghost"
              onClick={() => {
                setSearch("");
                setQuery("");
                setPage(1);
              }}
            >
              حذف جستجو
            </Button>
          ) : null}
        </form>
      </section>

      {orders.error && !orders.data ? (
        <ErrorState message={orders.error} onRetry={orders.reload} />
      ) : orders.loading && !orders.data ? (
        <SkeletonRows rows={5} />
      ) : (orders.data?.items.length ?? 0) === 0 ? (
        <section className="panel p-6">
          <EmptyState
            title="سفارشی در این فیلتر نیست"
            description="سفارش هایی که از دکمه «ثبت سفارش» ربات تلگرام ثبت می شوند اینجا نمایش داده می شوند."
            icon={<ClipboardList size={20} aria-hidden />}
          />
        </section>
      ) : (
        <section className="panel overflow-x-auto">
          <table className="w-full min-w-[720px] text-start text-[11px]">
            <thead>
              <tr className="border-b border-line-soft text-muted">
                <th className="px-3 py-2 text-start font-medium">کارفرما</th>
                <th className="px-3 py-2 text-start font-medium">خدمت</th>
                <th className="px-3 py-2 text-start font-medium">تماس</th>
                <th className="px-3 py-2 text-start font-medium">زمان ثبت</th>
                <th className="px-3 py-2 text-start font-medium">وضعیت</th>
                <th className="px-3 py-2 text-start font-medium" />
              </tr>
            </thead>
            <tbody>
              {(orders.data?.items ?? []).map((order) => (
                <tr key={order.id} className="border-b border-line-soft/60">
                  <td className="px-3 py-2.5">
                    <span className="font-medium">{order.contact_name}</span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="block">{order.item_title}</span>
                    <span className="text-[10px] text-muted">{order.category_title}</span>
                  </td>
                  <td className="px-3 py-2.5" dir="ltr">
                    {order.contact_phone}
                  </td>
                  <td className="px-3 py-2.5">{formatDateTime(order.created_at)}</td>
                  <td className="px-3 py-2.5">
                    <StatusBadge status={order.status} />
                  </td>
                  <td className="px-3 py-2.5 text-end">
                    <Button size="sm" variant="secondary" onClick={() => setSelected(order.id)}>
                      جزئیات
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {orders.data && orders.data.pages > 1 ? (
            <div className="flex items-center justify-between gap-2 px-3 py-3 text-[11px] text-muted">
              <span>
                صفحه {orders.data.page} از {orders.data.pages} · {orders.data.total} سفارش
              </span>
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  قبلی
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= orders.data.pages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  بعدی
                </Button>
              </div>
            </div>
          ) : null}
        </section>
      )}

      <OrderDetailModal
        orderId={selected}
        onClose={() => setSelected(null)}
        onChanged={reloadAll}
      />
    </div>
  );
}
