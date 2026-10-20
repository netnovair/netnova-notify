"use client";

import { CheckCircle2, Pencil, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { formatAmount } from "@/lib/format";
import type { Payment } from "@/types/api";

export function PaymentActions({
  payment,
  onEdit,
  onChanged,
}: {
  payment: Payment;
  onEdit: () => void;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [pending, setPending] = useState<null | "paid" | "cancel">(null);
  const [busy, setBusy] = useState(false);

  async function confirm(action: "paid" | "cancel") {
    setBusy(true);
    try {
      await api.post(`/payments/${payment.id}/${action === "paid" ? "mark-paid" : "cancel"}`);
      notify(
        action === "paid" ? "پرداخت به عنوان تسویه شده ثبت شد." : "پرداخت لغو شد.",
        "success",
      );
      onChanged();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  const editable = payment.status === "unpaid";

  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        {editable ? (
          <Button variant="secondary" size="sm" onClick={() => setPending("paid")}>
            <CheckCircle2 size={13} aria-hidden />
            تسویه شد
          </Button>
        ) : null}
        {editable ? (
          <Button variant="ghost" size="sm" onClick={onEdit}>
            <Pencil size={13} aria-hidden />
            ویرایش
          </Button>
        ) : null}
        {editable ? (
          <Button variant="ghost" size="sm" onClick={() => setPending("cancel")}>
            <XCircle size={13} aria-hidden />
            لغو
          </Button>
        ) : null}
        {!editable ? <span className="text-[11px] text-muted">اتمام یافته</span> : null}
      </div>

      <ConfirmDialog
        open={pending === "paid"}
        onClose={() => setPending(null)}
        onConfirm={() => confirm("paid")}
        loading={busy}
        title="ثبت تسویه پرداخت"
        message={`مبلغ ${formatAmount(payment.amount_minor, payment.currency)} به عنوان تسویه شده ثبت می شود و یادآوری زمان بندی شده لغو خواهد شد.`}
        confirmLabel="بله، تسویه شده"
      />
      <ConfirmDialog
        open={pending === "cancel"}
        onClose={() => setPending(null)}
        onConfirm={() => confirm("cancel")}
        loading={busy}
        tone="danger"
        title="لغو پرداخت"
        message="وضعیت پرداخت به «لغو شده» تغییر می کند و یادآوری زمان بندی شده حذف می شود. این عملیات در تاریخچه ثبت خواهد شد."
        confirmLabel="لغو پرداخت"
      />
    </>
  );
}
