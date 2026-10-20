"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { fromDateTimeInput, toDateInput } from "@/lib/format";
import { CURRENCY_OPTIONS } from "@/lib/labels";
import { amountToMinor, paymentSchema, type PaymentValues } from "@/lib/validation";
import type { Payment, ProjectListItem } from "@/types/api";

function defaultDue(): string {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return toDateInput(date.toISOString());
}

export function PaymentFormModal({
  open,
  onClose,
  projects,
  fixedProjectId,
  payment,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  projects: ProjectListItem[];
  fixedProjectId?: string;
  payment?: Payment;
  onSaved: (payment: Payment) => void;
}) {
  const { notify } = useToast();
  const isEdit = Boolean(payment);
  const [serverError, setServerError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState(fixedProjectId ?? projects[0]?.id ?? "");
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<PaymentValues>({
    resolver: zodResolver(paymentSchema),
    defaultValues: payment
      ? {
          title: payment.title,
          amount:
            payment.amount_minor /
            (payment.currency === "USD" || payment.currency === "EUR" ? 100 : 1),
          currency: payment.currency,
          due_at: toDateInput(payment.due_at),
          notes: payment.notes ?? "",
        }
      : {
          title: "",
          amount: undefined as unknown as number,
          currency: "IRT",
          due_at: defaultDue(),
          notes: "",
        },
  });

  const currency = watch("currency");

  async function onSubmit(values: PaymentValues) {
    if (!isEdit && !projectId) {
      setServerError("پروژه را انتخاب کنید.");
      return;
    }
    setServerError(null);
    const payload = {
      title: values.title,
      amount_minor: amountToMinor(values.amount, values.currency),
      currency: values.currency,
      due_at: fromDateTimeInput(`${values.due_at}T23:59`),
      notes: values.notes?.trim() ? values.notes : null,
    };
    try {
      const saved = isEdit && payment
        ? await api.patch<Payment>(`/payments/${payment.id}`, payload)
        : await api.post<Payment>(`/projects/${projectId}/payments`, payload);
      notify(isEdit ? "پرداخت ویرایش شد." : "پرداخت ثبت شد.", "success");
      onSaved(saved);
      onClose();
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "ویرایش پرداخت" : "ثبت پرداخت"}
      description={
        isEdit
          ? "وضعیت مالی پرداخت تسویه شده قابل ویرایش نیست."
          : "این فرم وضعیت مالی را ثبت می کند و به معنای دریافت وجه آنلاین نیست."
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            انصراف
          </Button>
          <Button onClick={() => void handleSubmit(onSubmit)()} loading={isSubmitting}>
            {isEdit ? "ذخیره تغییرات" : "ثبت پرداخت"}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        {serverError ? (
          <p
            role="alert"
            className="rounded-lg border border-danger/30 bg-danger/[0.07] px-3 py-2 text-xs leading-6 text-[#ffb4b4]"
          >
            {serverError}
          </p>
        ) : null}

        {!fixedProjectId && !isEdit ? (
          <div>
            <label htmlFor="payment-project" className="field-label">
              پروژه
            </label>
            <select
              id="payment-project"
              className="field-input"
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
            >
              {projects.length === 0 ? <option value="">پروژه ای وجود ندارد</option> : null}
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div>
          <label htmlFor="payment-title" className="field-label">
            عنوان پرداخت
          </label>
          <input
            id="payment-title"
            className="field-input"
            placeholder="مثلا پرداخت مرحله اول طراحی"
            aria-invalid={errors.title ? "true" : undefined}
            {...register("title")}
          />
          {errors.title ? <p className="field-error">{errors.title.message}</p> : null}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="payment-amount" className="field-label">
              مبلغ
            </label>
            <input
              id="payment-amount"
              type="number"
              inputMode="decimal"
              step={currency === "USD" || currency === "EUR" ? "0.01" : "1"}
              min="0"
              dir="ltr"
              className="field-input text-start"
              placeholder="5000000"
              aria-invalid={errors.amount ? "true" : undefined}
              {...register("amount", { valueAsNumber: true })}
            />
            {errors.amount ? <p className="field-error">{errors.amount.message}</p> : null}
          </div>
          <div>
            <label htmlFor="payment-currency" className="field-label">
              واحد پول
            </label>
            <select id="payment-currency" className="field-input" {...register("currency")}>
              {CURRENCY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} ({option.value})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label htmlFor="payment-due" className="field-label">
            تاریخ سررسید
          </label>
          <input
            id="payment-due"
            type="date"
            className="field-input"
            aria-invalid={errors.due_at ? "true" : undefined}
            {...register("due_at")}
          />
          {errors.due_at ? <p className="field-error">{errors.due_at.message}</p> : null}
          <p className="field-hint">
            یادآوری پرداخت به صورت خودکار چند روز قبل از سررسید برای کارفرما ارسال می شود.
            مبالغ تومان و ریال بدون اعشار و دلار و یورو تا دو رقم اعشار ثبت می شوند.
          </p>
        </div>

        <div>
          <label htmlFor="payment-notes" className="field-label">
            توضیحات <span className="font-normal text-muted">(اختیاری)</span>
          </label>
          <textarea
            id="payment-notes"
            rows={3}
            className="field-input resize-y"
            placeholder="توضیح کوتاه برای کارفرما"
            {...register("notes")}
          />
          {errors.notes ? <p className="field-error">{errors.notes.message}</p> : null}
        </div>

        <p className="rounded-xl border border-line-soft bg-elevated/40 px-3 py-2.5 text-[11px] leading-6 text-muted">
          مبلغ و واحد پول در پیام تلگرام و پنل به صورت صریح نمایش داده می شود. سیستم
          بدون اتصال به درگاه بانکی، تایید تراکنش ادعا نمی کند.
        </p>
      </form>
    </Modal>
  );
}
