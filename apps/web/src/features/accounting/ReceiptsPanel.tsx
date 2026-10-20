"use client";

import { Check, Eye, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { formatAmount, formatDateTime, formatNumber } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import { RECEIPT_STATUS } from "@/lib/labels";
import type {
  Currency,
  Page,
  Payment,
  PaymentReceipt,
  ProjectListItem,
  ReceiptStatus,
} from "@/types/api";

const STATUS_TABS: { key: ReceiptStatus | ""; label: string }[] = [
  { key: "pending", label: "در انتظار بررسی" },
  { key: "approved", label: "تایید شده" },
  { key: "rejected", label: "رد شده" },
  { key: "", label: "همه" },
];

function ReceiptThumb({ fileId }: { fileId: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    api
      .getBlob(`/accounting/receipt-files/${fileId}`)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!active) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId]);

  if (url) {
    return (
      <a href={url} target="_blank" rel="noreferrer" title="باز کردن تصویر رسید">
        <img src={url} alt="تصویر رسید" className="h-20 w-20 rounded-lg object-cover" />
      </a>
    );
  }
  if (failed) return <div className="h-20 w-20 rounded-lg bg-white/5 text-[10px]">خطا</div>;
  return <div className="h-20 w-20 animate-pulse rounded-lg bg-white/5" />;
}

type AllocationDraft = { paymentId: string; amount: number };

export function ReceiptsPanel({
  projects,
  refreshKey,
  onChanged,
}: {
  projects: ProjectListItem[];
  refreshKey: number;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [status, setStatus] = useState<ReceiptStatus | "">("pending");
  const [projectId, setProjectId] = useState("");
  const [detail, setDetail] = useState<PaymentReceipt | null>(null);
  const [review, setReview] = useState<{ receipt: PaymentReceipt; mode: "approve" | "reject" } | null>(
    null,
  );

  const receipts = useApiData<PaymentReceipt[]>(
    (signal) =>
      api.get<PaymentReceipt[]>(
        `/accounting/receipts?limit=100${status ? `&status=${status}` : ""}${
          projectId ? `&project_id=${projectId}` : ""
        }`,
        signal,
      ),
    [status, projectId, refreshKey],
  );

  const rows = receipts.data ?? [];

  return (
    <div className="space-y-4">
      <InlineAlert>
        تایید رسید یعنی «این مبلغ را دریافت کرده ایم»؛ سند بانکی به صورت خودکار بررسی نمی شود.
        پس از تایید، مبلغ به صورت پیش فرض به قدیمی ترین فاکتور باز تخصیص می یابد و باقی مانده به
        عنوان اعتبار پروژه ذخیره می شود.
      </InlineAlert>

      <div className="panel flex flex-col gap-2 p-3 sm:flex-row">
        <div className="flex flex-wrap gap-1">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.key || "all"}
              type="button"
              onClick={() => setStatus(tab.key)}
              className={
                status === tab.key
                  ? "rounded-lg bg-accent/15 px-3 py-1.5 text-xs text-accent"
                  : "rounded-lg px-3 py-1.5 text-xs text-muted transition hover:bg-white/5"
              }
            >
              {tab.label}
            </button>
          ))}
        </div>
        <select
          className="field-input sm:mr-auto sm:w-56"
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          aria-label="فیلتر پروژه"
        >
          <option value="">همه پروژه ها</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      {receipts.loading ? (
        <SkeletonRows rows={5} />
      ) : receipts.error ? (
        <ErrorState message={receipts.error} onRetry={receipts.reload} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="رسیدی در این وضعیت نیست"
          description="کارفرما می تواند از داخل ربات، رسید پرداخت و تصویر آن را ارسال کند."
        />
      ) : (
        <div className="panel overflow-x-auto p-0">
          <table className="w-full text-right text-xs">
            <thead className="text-muted">
              <tr className="border-b border-line/60">
                <th className="px-3 py-2 font-normal">تاریخ</th>
                <th className="px-3 py-2 font-normal">پروژه</th>
                <th className="px-3 py-2 font-normal">مبلغ</th>
                <th className="px-3 py-2 font-normal">کد پیگیری</th>
                <th className="px-3 py-2 font-normal">منبع</th>
                <th className="px-3 py-2 font-normal">وضعیت</th>
                <th className="px-3 py-2 font-normal">تصویر</th>
                <th className="px-3 py-2 font-normal" />
              </tr>
            </thead>
            <tbody>
              {rows.map((receipt) => {
                const spec = RECEIPT_STATUS[receipt.status];
                return (
                  <tr key={receipt.id} className="border-b border-line/30 hover:bg-white/5">
                    <td className="whitespace-nowrap px-3 py-3">{formatDateTime(receipt.created_at)}</td>
                    <td className="px-3 py-3">{receipt.project_name ?? "—"}</td>
                    <td className="whitespace-nowrap px-3 py-3">
                      {formatAmount(receipt.amount_minor, receipt.currency as Currency)}
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px]">
                      {receipt.tracking_code ?? "—"}
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {receipt.channel === "telegram" ? "ربات" : "پنل"}
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={spec.tone}>{spec.label}</Badge>
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {receipt.files.length ? `${receipt.files.length} فایل` : "—"}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => setDetail(receipt)}
                          className="rounded-lg p-1.5 text-muted transition hover:bg-white/5 hover:text-ink"
                          aria-label="مشاهده رسید"
                        >
                          <Eye size={15} aria-hidden />
                        </button>
                        {receipt.status === "pending" && (
                          <>
                            <button
                              type="button"
                              onClick={() => setReview({ receipt, mode: "approve" })}
                              className="rounded-lg p-1.5 text-success transition hover:bg-success/10"
                              aria-label="تایید رسید"
                            >
                              <Check size={15} aria-hidden />
                            </button>
                            <button
                              type="button"
                              onClick={() => setReview({ receipt, mode: "reject" })}
                              className="rounded-lg p-1.5 text-danger transition hover:bg-danger/10"
                              aria-label="رد رسید"
                            >
                              <X size={15} aria-hidden />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ReceiptDetail receipt={detail} onClose={() => setDetail(null)} />
      {review && (
        <ReviewModal
          receipt={review.receipt}
          mode={review.mode}
          onClose={() => setReview(null)}
          onDone={() => {
            setReview(null);
            receipts.reload();
            onChanged();
            notify(
              review.mode === "approve" ? "رسید تایید شد." : "رسید رد شد.",
              "success",
            );
          }}
        />
      )}
    </div>
  );
}

function ReceiptDetail({
  receipt,
  onClose,
}: {
  receipt: PaymentReceipt | null;
  onClose: () => void;
}) {
  return (
    <Modal open={Boolean(receipt)} onClose={onClose} title="جزئیات رسید" size="lg">
      {receipt && (
        <div className="space-y-4 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-muted">مبلغ</div>
              <div className="mt-1">
                {formatAmount(receipt.amount_minor, receipt.currency as Currency)}
              </div>
            </div>
            <div>
              <div className="text-muted">وضعیت</div>
              <div className="mt-1">
                <Badge tone={RECEIPT_STATUS[receipt.status].tone}>
                  {RECEIPT_STATUS[receipt.status].label}
                </Badge>
              </div>
            </div>
            <div>
              <div className="text-muted">کد پیگیری</div>
              <div className="mt-1 font-mono">{receipt.tracking_code ?? "—"}</div>
            </div>
            <div>
              <div className="text-muted">تاریخ ثبت</div>
              <div className="mt-1">{formatDateTime(receipt.created_at)}</div>
            </div>
          </div>
          {receipt.note && (
            <div>
              <div className="text-muted">توضیح کارفرما</div>
              <p className="mt-1 whitespace-pre-wrap leading-6">{receipt.note}</p>
            </div>
          )}
          {receipt.files.length > 0 && (
            <div>
              <div className="mb-2 text-muted">تصاویر رسید</div>
              <div className="flex flex-wrap gap-2">
                {receipt.files.map((file) => (
                  <ReceiptThumb key={file.id} fileId={file.id} />
                ))}
              </div>
            </div>
          )}
          {receipt.allocations.length > 0 && (
            <div>
              <div className="mb-1 text-muted">تخصیص به فاکتورها</div>
              <ul className="space-y-1">
                {receipt.allocations.map((allocation) => (
                  <li key={allocation.id} className="flex justify-between gap-2">
                    <span>{allocation.payment_title ?? "فاکتور"}</span>
                    <span>{formatAmount(allocation.amount_minor, receipt.currency as Currency)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {receipt.review_note && (
            <div>
              <div className="text-muted">یادداشت بررسی</div>
              <p className="mt-1 whitespace-pre-wrap leading-6">{receipt.review_note}</p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function ReviewModal({
  receipt,
  mode,
  onClose,
  onDone,
}: {
  receipt: PaymentReceipt;
  mode: "approve" | "reject";
  onClose: () => void;
  onDone: () => void;
}) {
  const { notify } = useToast();
  const [note, setNote] = useState("");
  const [auto, setAuto] = useState(true);
  const [drafts, setDrafts] = useState<AllocationDraft[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const invoices = useApiData<Page<Payment>>(
    (signal) =>
      api.get<Page<Payment>>(
        `/payments?project_id=${receipt.project_id}&page_size=100`,
        signal,
      ),
    [receipt.project_id],
  );

  const open = useMemo(
    () =>
      (invoices.data?.items ?? [])
        .filter((item) => item.status !== "cancelled" && item.remaining_minor > 0)
        .sort((a, b) => a.due_at.localeCompare(b.due_at)),
    [invoices.data],
  );

  useEffect(() => {
    // Suggest the same oldest-first split the server applies by default.
    let left = receipt.amount_minor;
    const next: AllocationDraft[] = [];
    for (const invoice of open) {
      if (left <= 0) break;
      const take = Math.min(left, invoice.remaining_minor);
      next.push({ paymentId: invoice.id, amount: take });
      left -= take;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDrafts(next);
  }, [open, receipt.amount_minor]);

  const allocated = drafts.reduce((sum, row) => sum + (row.amount || 0), 0);
  const over = allocated > receipt.amount_minor;
  const invalidInvoice = drafts.some((row) => {
    const invoice = open.find((item) => item.id === row.paymentId);
    return !invoice || row.amount < 0 || row.amount > invoice.remaining_minor;
  });

  async function submit() {
    setSubmitting(true);
    try {
      if (mode === "reject") {
        await api.post(`/accounting/receipts/${receipt.id}/reject`, { note });
      } else {
        const allocations = auto
          ? null
          : drafts
              .filter((row) => row.amount > 0)
              .map((row) => ({
                payment_id: row.paymentId,
                amount_minor: Math.round(row.amount),
              }));
        await api.post(`/accounting/receipts/${receipt.id}/approve`, {
          note,
          allocations,
        });
      }
      onDone();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  const disabled =
    submitting ||
    (mode === "reject" && note.trim().length < 3) ||
    (mode === "approve" && !auto && (over || invalidInvoice || allocated <= 0));

  return (
    <Modal
      open
      onClose={onClose}
      title={mode === "approve" ? "تایید رسید پرداخت" : "رد رسید پرداخت"}
      description={`${receipt.project_name ?? ""} · ${formatAmount(
        receipt.amount_minor,
        receipt.currency as Currency,
      )}`}
      size="lg"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="h-9 rounded-lg border border-line px-3 text-xs text-ink transition hover:bg-white/5 disabled:opacity-50"
          >
            انصراف
          </button>
          <Button
            onClick={() => void submit()}
            loading={submitting}
            disabled={disabled}
            variant={mode === "approve" ? "primary" : "danger"}
          >
            {mode === "approve" ? "تایید و ثبت پرداخت" : "رد رسید"}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-xs">
        {mode === "approve" ? (
          <>
            <div className="space-y-2 rounded-xl border border-line/60 p-3">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={auto}
                  onChange={(event) => setAuto(event.target.checked)}
                />
                <span>
                  تخصیص خودکار (قدیمی ترین سررسید اول)
                  {allocated > receipt.amount_minor && (
                    <span className="text-danger"> — مبلغ تخصیص از رسید بیشتر است</span>
                  )}
                </span>
              </label>
              {auto && (
                <p className="text-[11px] text-muted">
                  {open.length === 0
                    ? "فاکتور بازی وجود ندارد."
                    : `${formatNumber(allocated)} از ${formatNumber(receipt.amount_minor)} به ${
                        drafts.length
                      } فاکتور تخصیص می یابد.`}
                </p>
              )}
            </div>

            {!auto && (
              <div className="space-y-2">
                <p className="text-muted">مبلغ هر فاکتور را مشخص کنید (خالی = بدون تخصیص).</p>
                {open.length === 0 && (
                  <p className="text-warning">فاکتور بازی برای این پروژه وجود ندارد.</p>
                )}
                {open.map((invoice) => {
                  const draft = drafts.find((row) => row.paymentId === invoice.id);
                  return (
                    <div
                      key={invoice.id}
                      className="flex flex-col gap-2 rounded-lg border border-line/50 p-2 sm:flex-row sm:items-center"
                    >
                      <div className="flex-1">
                        <div>{invoice.title}</div>
                        <div className="text-[11px] text-muted">
                          مانده: {formatAmount(invoice.remaining_minor, invoice.currency as Currency)}
                        </div>
                      </div>
                      <input
                        className="field-input sm:w-40"
                        inputMode="numeric"
                        value={draft?.amount ?? ""}
                        onChange={(event) => {
                          const value = Number(
                            event.target.value.replace(/[^0-9]/g, "") || 0,
                          );
                          setDrafts((previous) => {
                            const others = previous.filter(
                              (row) => row.paymentId !== invoice.id,
                            );
                            return value > 0
                              ? [...others, { paymentId: invoice.id, amount: value }]
                              : others;
                          });
                        }}
                        aria-label={`مبلغ تخصیص ${invoice.title}`}
                      />
                    </div>
                  );
                })}
                <p className={over ? "text-danger" : "text-muted"}>
                  جمع تخصیص: {formatNumber(allocated)} از {formatNumber(receipt.amount_minor)}
                </p>
              </div>
            )}
          </>
        ) : (
          <label className="block">
            <span className="text-muted">دلیل رد (برای کارفرما ارسال می شود)</span>
            <textarea
              className="field-input mt-1 min-h-[90px]"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="مثلا: تصویر رسید خوانا نیست."
            />
          </label>
        )}

        {mode === "approve" && (
          <label className="block">
            <span className="text-muted">یادداشت داخلی (اختیاری)</span>
            <textarea
              className="field-input mt-1 min-h-[70px]"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
        )}

        {mode === "approve" && (
          <p className="text-[11px] text-muted">
            جمع تخصیص نباید از مبلغ رسید بیشتر شود؛ مبلغی که تخصیص نیابد به عنوان اعتبار پروژه
            نگه داشته می شود.
          </p>
        )}
      </div>
    </Modal>
  );
}
