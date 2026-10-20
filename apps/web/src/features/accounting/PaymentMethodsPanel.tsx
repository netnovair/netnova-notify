"use client";

import { CreditCard, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import type { PaymentMethod, ProjectListItem } from "@/types/api";

type Draft = {
  id?: string;
  project_id: string;
  title: string;
  card_number: string;
  holder_name: string;
  bank_name: string;
  note: string;
  is_active: boolean;
  order_index: number;
};

const EMPTY: Draft = {
  project_id: "",
  title: "",
  card_number: "",
  holder_name: "",
  bank_name: "",
  note: "",
  is_active: true,
  order_index: 0,
};

export function PaymentMethodsPanel({
  projects,
  refreshKey,
  onChanged,
}: {
  projects: ProjectListItem[];
  refreshKey: number;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [scope, setScope] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [removing, setRemoving] = useState<PaymentMethod | null>(null);
  const [saving, setSaving] = useState(false);

  const methods = useApiData<PaymentMethod[]>(
    (signal) =>
      api.get<PaymentMethod[]>(
        `/accounting/payment-methods${scope ? `?project_id=${scope}` : ""}`,
        signal,
      ),
    [scope, refreshKey],
  );

  async function save() {
    if (!draft) return;
    setSaving(true);
    try {
      const payload = {
        project_id: draft.project_id || null,
        title: draft.title.trim(),
        card_number: draft.card_number.replace(/[\s-]/g, ""),
        holder_name: draft.holder_name.trim(),
        bank_name: draft.bank_name.trim(),
        note: draft.note.trim(),
        is_active: draft.is_active,
        order_index: draft.order_index,
      };
      if (draft.id) {
        await api.patch(`/accounting/payment-methods/${draft.id}`, payload);
      } else {
        await api.post("/accounting/payment-methods", payload);
      }
      setDraft(null);
      methods.reload();
      onChanged();
      notify("شماره کارت ذخیره شد.", "success");
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!removing) return;
    setSaving(true);
    try {
      await api.del(`/accounting/payment-methods/${removing.id}`);
      setRemoving(null);
      methods.reload();
      onChanged();
      notify("شماره کارت حذف شد.", "success");
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setSaving(false);
    }
  }

  const rows = methods.data ?? [];
  const scoped = rows.filter((row) => row.project_id === scope || (!scope && row.project_id));
  const global = rows.filter((row) => !row.project_id);
  const visible = scope ? rows : [...scoped, ...global];

  return (
    <div className="space-y-4">
      <InlineAlert>
        این شماره کارت ها در بخش «ارسال رسید» ربات به کارفرما نشان داده می شوند. شماره کارت
        اختصاصی پروژه، جای شماره های عمومی را می گیرد؛ اگر پروژه شماره اختصاصی نداشته باشد
        شماره های عمومی نمایش داده می شوند.
      </InlineAlert>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          className="field-input sm:w-64"
          value={scope}
          onChange={(event) => setScope(event.target.value)}
          aria-label="انتخاب پروژه"
        >
          <option value="">شماره های عمومی</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <Button className="sm:mr-auto" onClick={() => setDraft({ ...EMPTY, project_id: scope })}>
          <Plus size={16} aria-hidden />
          افزودن شماره کارت
        </Button>
      </div>

      {methods.loading ? (
        <SkeletonRows rows={4} />
      ) : methods.error ? (
        <ErrorState message={methods.error} onRetry={methods.reload} />
      ) : visible.length === 0 ? (
        <EmptyState
          title="شماره کارتی ثبت نشده است"
          description="برای نمایش در ربات، حداقل یک شماره کارت عمومی یا مخصوص پروژه اضافه کنید."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visible.map((method) => (
            <div key={method.id} className="panel space-y-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CreditCard size={16} className="text-[#b9a7ff]" aria-hidden />
                  <span className="text-sm">{method.title}</span>
                </div>
                <div className="flex items-center gap-1">
                  {method.project_id ? (
                    <Badge tone="accent">
                      {projects.find((project) => project.id === method.project_id)?.name ??
                        "پروژه"}
                    </Badge>
                  ) : (
                    <Badge tone="neutral">عمومی</Badge>
                  )}
                  {!method.is_active && <Badge tone="warning">غیرفعال</Badge>}
                </div>
              </div>
              <div className="font-mono text-sm tracking-wider" dir="ltr">
                {method.card_number.replace(/(.{4})/g, "$1 ").trim()}
              </div>
              <div className="text-[11px] text-muted">
                {[method.bank_name, method.holder_name].filter(Boolean).join(" · ") || "—"}
              </div>
              {method.note && <p className="text-[11px] leading-5 text-muted">{method.note}</p>}
              <div className="flex gap-1 pt-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setDraft({
                      id: method.id,
                      project_id: method.project_id ?? "",
                      title: method.title,
                      card_number: method.card_number,
                      holder_name: method.holder_name,
                      bank_name: method.bank_name,
                      note: method.note,
                      is_active: method.is_active,
                      order_index: method.order_index,
                    })
                  }
                >
                  ویرایش
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRemoving(method)}>
                  <Trash2 size={14} aria-hidden />
                  حذف
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={Boolean(draft)}
        onClose={() => setDraft(null)}
        title={draft?.id ? "ویرایش شماره کارت" : "افزودن شماره کارت"}
        footer={
          <>
            <button
              type="button"
              onClick={() => setDraft(null)}
              disabled={saving}
              className="h-9 rounded-lg border border-line px-3 text-xs text-ink transition hover:bg-white/5 disabled:opacity-50"
            >
              انصراف
            </button>
            <Button
              onClick={() => void save()}
              loading={saving}
              disabled={!draft?.title.trim() || !draft.card_number.trim()}
            >
              ذخیره
            </Button>
          </>
        }
      >
        {draft && (
          <div className="grid gap-3 text-xs sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="text-muted">عنوان</span>
              <input
                className="field-input mt-1"
                value={draft.title}
                onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                placeholder="مثلا: کارت بانک ملی"
              />
            </label>
            <label className="sm:col-span-2">
              <span className="text-muted">شماره کارت</span>
              <input
                className="field-input mt-1 font-mono"
                dir="ltr"
                inputMode="numeric"
                value={draft.card_number}
                onChange={(event) => setDraft({ ...draft, card_number: event.target.value })}
                placeholder="6037997711223344"
              />
            </label>
            <label>
              <span className="text-muted">نام بانک</span>
              <input
                className="field-input mt-1"
                value={draft.bank_name}
                onChange={(event) => setDraft({ ...draft, bank_name: event.target.value })}
              />
            </label>
            <label>
              <span className="text-muted">نام صاحب حساب</span>
              <input
                className="field-input mt-1"
                value={draft.holder_name}
                onChange={(event) => setDraft({ ...draft, holder_name: event.target.value })}
              />
            </label>
            <label className="sm:col-span-2">
              <span className="text-muted">توضیح کوتاه</span>
              <input
                className="field-input mt-1"
                value={draft.note}
                onChange={(event) => setDraft({ ...draft, note: event.target.value })}
                placeholder="مثلا: پس از واریز، رسید را ارسال کنید."
              />
            </label>
            <label>
              <span className="text-muted">پروژه</span>
              <select
                className="field-input mt-1"
                value={draft.project_id}
                onChange={(event) => setDraft({ ...draft, project_id: event.target.value })}
              >
                <option value="">عمومی (همه پروژه ها)</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="text-muted">ترتیب نمایش</span>
              <input
                className="field-input mt-1"
                type="number"
                min={0}
                value={draft.order_index}
                onChange={(event) =>
                  setDraft({ ...draft, order_index: Number(event.target.value || 0) })
                }
              />
            </label>
            <label className="flex items-center gap-2 sm:col-span-2">
              <input
                type="checkbox"
                checked={draft.is_active}
                onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })}
              />
              <span>نمایش این شماره کارت در ربات</span>
            </label>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(removing)}
        onClose={() => setRemoving(null)}
        onConfirm={remove}
        title="حذف شماره کارت"
        message="این شماره کارت دیگر در ربات نمایش داده نمی شود. ادامه می دهید؟"
        confirmLabel="حذف"
        tone="danger"
        loading={saving}
      />
    </div>
  );
}
