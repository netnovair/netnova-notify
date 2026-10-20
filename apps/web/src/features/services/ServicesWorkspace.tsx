"use client";

import { Layers, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import { QUESTION_TYPES } from "@/lib/labels";
import type {
  ServiceCatalog,
  ServiceCategory,
  ServiceCategoryInput,
  ServiceItem,
  ServiceItemInput,
  ServiceQuestionInput,
  ServiceQuestionType,
} from "@/types/api";

type CategoryDraft = {
  id: string | null;
  title: string;
  emoji: string;
  description: string;
  order_index: string;
  is_active: boolean;
  show_portfolio: boolean;
  portfolio_text: string;
  portfolio_url: string;
};

type QuestionDraft = {
  key: string;
  label: string;
  help_text: string;
  field_type: ServiceQuestionType;
  required: boolean;
  options: string;
  min_value: string;
  max_value: string;
};

type ItemDraft = {
  id: string | null;
  categoryId: string;
  title: string;
  description: string;
  order_index: string;
  is_active: boolean;
  show_portfolio: boolean;
  portfolio_text: string;
  portfolio_url: string;
  questions: QuestionDraft[];
};

const EMPTY_CATEGORY: CategoryDraft = {
  id: null,
  title: "",
  emoji: "",
  description: "",
  order_index: "0",
  is_active: true,
  show_portfolio: false,
  portfolio_text: "",
  portfolio_url: "",
};

const EMPTY_QUESTION: QuestionDraft = {
  key: "",
  label: "",
  help_text: "",
  field_type: "text",
  required: true,
  options: "",
  min_value: "",
  max_value: "",
};

function toCategoryInput(draft: CategoryDraft): ServiceCategoryInput {
  return {
    title: draft.title.trim(),
    emoji: draft.emoji.trim(),
    description: draft.description.trim(),
    order_index: Number(draft.order_index) || 0,
    is_active: draft.is_active,
    show_portfolio: draft.show_portfolio,
    portfolio_text: draft.portfolio_text.trim(),
    portfolio_url: draft.portfolio_url.trim(),
  };
}

function toQuestions(draft: ItemDraft): ServiceQuestionInput[] {
  return draft.questions
    .filter((question) => question.label.trim().length >= 2)
    .map((question, index) => ({
      key: question.key.trim() || null,
      label: question.label.trim(),
      help_text: question.help_text.trim(),
      field_type: question.field_type,
      required: question.required,
      options:
        question.field_type === "choice"
          ? question.options
              .split(/[,،\n]/)
              .map((option) => option.trim())
              .filter(Boolean)
          : [],
      min_value: question.field_type === "number" && question.min_value !== ""
        ? Number(question.min_value)
        : null,
      max_value: question.field_type === "number" && question.max_value !== ""
        ? Number(question.max_value)
        : null,
      order_index: index,
      is_active: true,
    }));
}

function toItemInput(draft: ItemDraft): ServiceItemInput {
  return {
    title: draft.title.trim(),
    description: draft.description.trim(),
    order_index: Number(draft.order_index) || 0,
    is_active: draft.is_active,
    show_portfolio: draft.show_portfolio,
    portfolio_text: draft.portfolio_text.trim(),
    portfolio_url: draft.portfolio_url.trim(),
    questions: toQuestions(draft),
  };
}

function CategoryModal({
  draft,
  busy,
  onClose,
  onSave,
}: {
  draft: CategoryDraft;
  busy: boolean;
  onClose: () => void;
  onSave: (draft: CategoryDraft) => void;
}) {
  // The parent mounts this component on open, so props seed the state exactly once.
  const [form, setForm] = useState<CategoryDraft>(draft);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    if (form.title.trim().length < 2) {
      setError("عنوان خدمت باید حداقل ۲ حرف باشد.");
      return;
    }
    onSave(form);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={draft.id ? "ویرایش خدمت اصلی" : "خدمت اصلی جدید"}
      description="تغییرات بلافاصله در منوی «ثبت سفارش» ربات اعمال می شود."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            انصراف
          </Button>
          <Button onClick={submit} loading={busy}>
            ذخیره
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
        <div className="grid gap-4 sm:grid-cols-[1fr_90px]">
          <div>
            <label htmlFor="category-title" className="field-label">
              عنوان خدمت
            </label>
            <input
              id="category-title"
              className="field-input"
              placeholder="مثلا طراحی سایت"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
            />
          </div>
          <div>
            <label htmlFor="category-emoji" className="field-label">
              ایموجی
            </label>
            <input
              id="category-emoji"
              className="field-input text-center"
              placeholder="🎨"
              value={form.emoji}
              onChange={(event) => setForm({ ...form, emoji: event.target.value })}
            />
          </div>
        </div>
        <div>
          <label htmlFor="category-description" className="field-label">
            توضیح کوتاه
          </label>
          <textarea
            id="category-description"
            className="field-input min-h-20 resize-y"
            placeholder="این توضیح در فهرست خدمات و ابتدای گفتگو نمایش داده می شود."
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="category-order" className="field-label">
              ترتیب نمایش
            </label>
            <input
              id="category-order"
              type="number"
              min={0}
              className="field-input"
              value={form.order_index}
              onChange={(event) => setForm({ ...form, order_index: event.target.value })}
            />
            <p className="field-hint">عدد کوچک تر بالاتر نمایش داده می شود.</p>
          </div>
          <div className="space-y-2 pt-6">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              نمایش این خدمت در ربات
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={form.show_portfolio}
                onChange={(event) =>
                  setForm({ ...form, show_portfolio: event.target.checked })
                }
              />
              نمایش دکمه نمونه کار
            </label>
          </div>
        </div>
        {form.show_portfolio ? (
          <div>
            <label htmlFor="category-portfolio" className="field-label">
              متن نمونه کارها
            </label>
            <textarea
              id="category-portfolio"
              className="field-input min-h-24 resize-y"
              placeholder="نمونه کارهایی که در ربات نمایش داده می شود؛ لینک یا توضیح."
              value={form.portfolio_text}
              onChange={(event) => setForm({ ...form, portfolio_text: event.target.value })}
            />
            <p className="field-hint">
              فقط نمونه کارهای واقعی را وارد کنید؛ این متن عینا برای کارفرما ارسال می شود.
            </p>
            <label htmlFor="category-portfolio-url" className="field-label mt-3">
              لینک تصویر نمونه کار (اختیاری)
            </label>
            <input
              id="category-portfolio-url"
              dir="ltr"
              className="field-input text-start"
              placeholder="https://..."
              value={form.portfolio_url}
              onChange={(event) => setForm({ ...form, portfolio_url: event.target.value })}
            />
            <p className="field-hint">
              تصویر باید عمومی و با https در دسترس باشد؛ تلگرام خودش آن را نمایش می دهد.
            </p>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}

function QuestionRow({
  question,
  index,
  onChange,
  onRemove,
}: {
  question: QuestionDraft;
  index: number;
  onChange: (next: QuestionDraft) => void;
  onRemove: () => void;
}) {
  const inputId = `question-${index}-label`;
  return (
    <div className="rounded-xl border border-line-soft bg-white/[0.02] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[11px] text-muted">سوال {index + 1}</span>
        <Button
          size="sm"
          variant="ghost"
          className="ms-auto"
          onClick={onRemove}
          aria-label={`حذف سوال ${index + 1}`}
        >
          <Trash2 size={13} aria-hidden />
        </Button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label htmlFor={inputId} className="field-label">
            متن سوال
          </label>
          <input
            id={inputId}
            className="field-input"
            placeholder="مثلا لوگوی فعلی دارید؟"
            value={question.label}
            onChange={(event) => onChange({ ...question, label: event.target.value })}
          />
        </div>
        <div>
          <label className="field-label" htmlFor={`question-${index}-type`}>
            نوع پاسخ
          </label>
          <select
            id={`question-${index}-type`}
            className="field-input"
            value={question.field_type}
            onChange={(event) =>
              onChange({
                ...question,
                field_type: event.target.value as ServiceQuestionType,
              })
            }
          >
            {Object.entries(QUESTION_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end pb-2">
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={question.required}
              onChange={(event) => onChange({ ...question, required: event.target.checked })}
            />
            پاسخ به این سوال الزامی است
          </label>
        </div>
        {question.field_type === "choice" ? (
          <div className="sm:col-span-2">
            <label className="field-label" htmlFor={`question-${index}-options`}>
              گزینه ها (با ویرگول جدا کنید)
            </label>
            <input
              id={`question-${index}-options`}
              className="field-input"
              placeholder="افقی، عمودی، مربعی"
              value={question.options}
              onChange={(event) => onChange({ ...question, options: event.target.value })}
            />
          </div>
        ) : null}
        {question.field_type === "number" ? (
          <div className="grid grid-cols-2 gap-3 sm:col-span-2">
            <div>
              <label className="field-label" htmlFor={`question-${index}-min`}>
                حداقل مقدار
              </label>
              <input
                id={`question-${index}-min`}
                type="number"
                className="field-input"
                placeholder="مثلا 800"
                value={question.min_value}
                onChange={(event) => onChange({ ...question, min_value: event.target.value })}
              />
            </div>
            <div>
              <label className="field-label" htmlFor={`question-${index}-max`}>
                حداکثر مقدار
              </label>
              <input
                id={`question-${index}-max`}
                type="number"
                className="field-input"
                placeholder="اختیاری"
                value={question.max_value}
                onChange={(event) => onChange({ ...question, max_value: event.target.value })}
              />
            </div>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <label className="field-label" htmlFor={`question-${index}-help`}>
            راهنمای سوال (اختیاری)
          </label>
          <input
            id={`question-${index}-help`}
            className="field-input"
            placeholder="مثلا حداقل ۸۰۰ کلمه"
            value={question.help_text}
            onChange={(event) => onChange({ ...question, help_text: event.target.value })}
          />
        </div>
      </div>
    </div>
  );
}

function ItemModal({
  draft,
  busy,
  onClose,
  onSave,
}: {
  draft: ItemDraft;
  busy: boolean;
  onClose: () => void;
  onSave: (draft: ItemDraft) => void;
}) {
  const [form, setForm] = useState<ItemDraft>(draft);
  const [error, setError] = useState<string | null>(null);

  function updateQuestion(index: number, next: QuestionDraft) {
    const questions = form.questions.map((question, position) =>
      position === index ? next : question,
    );
    setForm({ ...form, questions });
  }

  function submit() {
    if (form.title.trim().length < 2) {
      setError("عنوان زیرخدمت باید حداقل ۲ حرف باشد.");
      return;
    }
    const invalidChoice = form.questions.find(
      (question) =>
        question.field_type === "choice" &&
        question.options
          .split(/[,،\n]/)
          .map((option) => option.trim())
          .filter(Boolean).length < 2,
    );
    if (invalidChoice) {
      setError("سوال های انتخابی باید حداقل دو گزینه داشته باشند.");
      return;
    }
    const invalidRange = form.questions.find(
      (question) =>
        question.field_type === "number" &&
        question.min_value !== "" &&
        question.max_value !== "" &&
        Number(question.min_value) > Number(question.max_value),
    );
    if (invalidRange) {
      setError("حداقل مقدار سوال عددی نمی تواند از حداکثر بیشتر باشد.");
      return;
    }
    onSave(form);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={draft.id ? "ویرایش زیرخدمت" : "زیرخدمت جدید"}
      description="سوال ها به ترتیب همین فهرست در ربات پرسیده می شوند."
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            انصراف
          </Button>
          <Button onClick={submit} loading={busy}>
            ذخیره
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
        <div>
          <label htmlFor="item-title" className="field-label">
            عنوان زیرخدمت
          </label>
          <input
            id="item-title"
            className="field-input"
            placeholder="مثلا طراحی لوگو"
            value={form.title}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
          />
        </div>
        <div>
          <label htmlFor="item-description" className="field-label">
            توضیح کوتاه
          </label>
          <textarea
            id="item-description"
            className="field-input min-h-16 resize-y"
            placeholder="این توضیح پیش از شروع سوال ها ارسال می شود."
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="item-order" className="field-label">
              ترتیب
            </label>
            <input
              id="item-order"
              type="number"
              min={0}
              className="field-input"
              value={form.order_index}
              onChange={(event) => setForm({ ...form, order_index: event.target.value })}
            />
          </div>
          <div className="space-y-2 pt-6">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              فعال در ربات
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={form.show_portfolio}
                onChange={(event) =>
                  setForm({ ...form, show_portfolio: event.target.checked })
                }
              />
              دکمه نمونه کار
            </label>
          </div>
          {form.show_portfolio ? (
            <div>
              <label htmlFor="item-portfolio" className="field-label">
                متن نمونه کار
              </label>
              <textarea
                id="item-portfolio"
                className="field-input min-h-16 resize-y"
                value={form.portfolio_text}
                onChange={(event) => setForm({ ...form, portfolio_text: event.target.value })}
              />
              <label htmlFor="item-portfolio-url" className="field-label mt-2">
                لینک تصویر (اختیاری)
              </label>
              <input
                id="item-portfolio-url"
                dir="ltr"
                className="field-input text-start"
                placeholder="https://..."
                value={form.portfolio_url}
                onChange={(event) =>
                  setForm({ ...form, portfolio_url: event.target.value })
                }
              />
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-line-soft p-3">
          <div className="mb-2 flex items-center gap-2">
            <h3 className="text-xs font-semibold">سوال های این زیرخدمت</h3>
            <Button
              size="sm"
              variant="secondary"
              className="ms-auto"
              onClick={() =>
                setForm({ ...form, questions: [...form.questions, { ...EMPTY_QUESTION }] })
              }
            >
              <Plus size={13} aria-hidden /> سوال
            </Button>
          </div>
          {form.questions.length === 0 ? (
            <p className="py-3 text-center text-[11px] text-muted">
              هنوز سوالی ثبت نشده است؛ فقط نام و شماره تماس پرسیده می شود.
            </p>
          ) : (
            <div className="space-y-2">
              {form.questions.map((question, index) => (
                <QuestionRow
                  key={index}
                  index={index}
                  question={question}
                  onChange={(next) => updateQuestion(index, next)}
                  onRemove={() =>
                    setForm({
                      ...form,
                      questions: form.questions.filter((_, position) => position !== index),
                    })
                  }
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

export function ServicesWorkspace() {
  const { notify } = useToast();
  const catalog = useApiData<ServiceCatalog>(
    (signal) => api.get<ServiceCatalog>("/catalog", signal),
    [],
  );
  const [categoryDraft, setCategoryDraft] = useState<CategoryDraft | null>(null);
  const [itemDraft, setItemDraft] = useState<ItemDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveCategory(draft: CategoryDraft) {
    setBusy(true);
    setError(null);
    try {
      const payload = toCategoryInput(draft);
      if (draft.id) {
        await api.patch(`/catalog/categories/${draft.id}`, payload);
      } else {
        await api.post("/catalog/categories", payload);
      }
      notify("خدمت اصلی ذخیره شد.", "success");
      setCategoryDraft(null);
      catalog.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveItem(draft: ItemDraft) {
    setBusy(true);
    setError(null);
    try {
      const payload = toItemInput(draft);
      if (draft.id) {
        await api.patch(`/catalog/items/${draft.id}`, payload);
      } else {
        await api.post(`/catalog/categories/${draft.categoryId}/items`, payload);
      }
      notify("زیرخدمت ذخیره شد.", "success");
      setItemDraft(null);
      catalog.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeCategory(category: ServiceCategory) {
    const confirmed = window.confirm(
      `خدمت «${category.title}» و زیرخدمت های آن حذف شود؟ این کار قابل بازگشت نیست.`,
    );
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      await api.del(`/catalog/categories/${category.id}`);
      notify("خدمت حذف شد.", "success");
      catalog.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeItem(item: ServiceItem) {
    const confirmed = window.confirm(`زیرخدمت «${item.title}» حذف شود؟`);
    if (!confirmed) return;
    setBusy(true);
    setError(null);
    try {
      await api.del(`/catalog/items/${item.id}`);
      notify("زیرخدمت حذف شد.", "success");
      catalog.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function seed() {
    setSeeding(true);
    setError(null);
    try {
      await api.post("/catalog/seed");
      notify("کاتالوگ پیش فرض نصب شد. از این پس می توانید آن را ویرایش کنید.", "success");
      catalog.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSeeding(false);
    }
  }

  const categories = catalog.data?.categories ?? [];

  return (
    <div className="space-y-4">
      <section className="panel flex flex-wrap items-center gap-3 p-4">
        <Layers size={18} className="text-[#b9a7ff]" aria-hidden />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">ساختار خدمات در ربات</h2>
          <p className="mt-0.5 text-[11px] leading-6 text-muted">
            هر تغییری در این صفحه، از پیام بعدی کارفرما در تلگرام دیده می شود و نیازی به
            انتشار مجدد ربات نیست.
          </p>
        </div>
        <div className="ms-auto flex flex-wrap items-center gap-2">
          {catalog.data && !catalog.data.seeded ? (
            <Button variant="secondary" onClick={seed} loading={seeding}>
              <Sparkles size={14} aria-hidden /> نصب کاتالوگ پیش فرض
            </Button>
          ) : null}
          <Button onClick={() => setCategoryDraft({ ...EMPTY_CATEGORY })}>
            <Plus size={14} aria-hidden /> خدمت اصلی
          </Button>
        </div>
      </section>

      {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}

      {catalog.error && !catalog.data ? (
        <ErrorState message={catalog.error} onRetry={catalog.reload} />
      ) : catalog.loading && !catalog.data ? (
        <SkeletonRows rows={4} />
      ) : categories.length === 0 ? (
        <section className="panel p-6">
          <EmptyState
            title="هنوز خدمتی تعریف نشده است"
            description="با نصب کاتالوگ پیش فرض، پنج خدمت گرافیک، سایت، اپلیکیشن، محتوا و سئو با سوال های آماده ساخته می شود. بعد از آن هر بخش را می توانید ویرایش کنید."
            action={
              <Button onClick={seed} loading={seeding}>
                <Sparkles size={14} aria-hidden /> نصب کاتالوگ پیش فرض
              </Button>
            }
          />
        </section>
      ) : (
        <div className="space-y-3">
          {categories.map((category) => (
            <section key={category.id} className="panel p-4">
              <div className="flex flex-wrap items-start gap-2">
                <span className="text-xl" aria-hidden>
                  {category.emoji || "•"}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="text-sm font-semibold">{category.title}</h3>
                    {category.is_active ? (
                      <Badge tone="success">فعال</Badge>
                    ) : (
                      <Badge tone="neutral">غیرفعال</Badge>
                    )}
                    {category.show_portfolio ? <Badge tone="info">نمونه کار</Badge> : null}
                    <Badge tone="neutral">{category.items.length} زیرخدمت</Badge>
                  </div>
                  <p className="mt-1 text-[11px] leading-6 text-muted">
                    {category.description || "بدون توضیح"}
                  </p>
                </div>
                <div className="ms-auto flex flex-wrap items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      setItemDraft({
                        id: null,
                        categoryId: category.id,
                        title: "",
                        description: "",
                        order_index: String(category.items.length),
                        is_active: true,
                        show_portfolio: false,
                        portfolio_text: "",
                        portfolio_url: "",
                        questions: [{ ...EMPTY_QUESTION }],
                      })
                    }
                  >
                    <Plus size={13} aria-hidden /> زیرخدمت
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setCategoryDraft({
                        id: category.id,
                        title: category.title,
                        emoji: category.emoji,
                        description: category.description,
                        order_index: String(category.order_index),
                        is_active: category.is_active,
                        show_portfolio: category.show_portfolio,
                        portfolio_text: category.portfolio_text,
                        portfolio_url: category.portfolio_url,
                      })
                    }
                    aria-label={`ویرایش ${category.title}`}
                  >
                    <Pencil size={13} aria-hidden />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void removeCategory(category)}
                    disabled={busy}
                    aria-label={`حذف ${category.title}`}
                  >
                    <Trash2 size={13} aria-hidden />
                  </Button>
                </div>
              </div>

              <ul className="mt-3 divide-y divide-line-soft border-t border-line-soft">
                {category.items.length === 0 ? (
                  <li className="py-3 text-[11px] text-muted">
                    زیرخدمتی ندارد؛ تا زمانی که زیرخدمت فعال اضافه نشود، این خدمت در ربات
                    نمایش داده نمی شود.
                  </li>
                ) : (
                  category.items.map((item) => (
                    <li
                      key={item.id}
                      className="flex flex-wrap items-center gap-2 py-2.5"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="text-xs font-medium">{item.title}</span>
                          {item.is_active ? (
                            <Badge tone="success">فعال</Badge>
                          ) : (
                            <Badge tone="neutral">غیرفعال</Badge>
                          )}
                          <Badge tone="neutral">{item.questions.length} سوال</Badge>
                          {item.show_portfolio ? (
                            <Badge tone="info">نمونه کار</Badge>
                          ) : null}
                        </div>
                        <p className="mt-0.5 text-[10px] text-muted">
                          {item.description || "بدون توضیح"}
                        </p>
                      </div>
                      <div className="ms-auto flex items-center gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            setItemDraft({
                              id: item.id,
                              categoryId: category.id,
                              title: item.title,
                              description: item.description,
                              order_index: String(item.order_index),
                              is_active: item.is_active,
                              show_portfolio: item.show_portfolio,
                              portfolio_text: item.portfolio_text,
                              portfolio_url: item.portfolio_url,
                              questions: item.questions.map((question) => ({
                                key: question.key,
                                label: question.label,
                                help_text: question.help_text,
                                field_type: question.field_type,
                                required: question.required,
                                options: question.options.join("، "),
                                min_value:
                                  question.min_value === null
                                    ? ""
                                    : String(question.min_value),
                                max_value:
                                  question.max_value === null
                                    ? ""
                                    : String(question.max_value),
                              })),
                            })
                          }
                          aria-label={`ویرایش ${item.title}`}
                        >
                          <Pencil size={13} aria-hidden />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void removeItem(item)}
                          disabled={busy}
                          aria-label={`حذف ${item.title}`}
                        >
                          <Trash2 size={13} aria-hidden />
                        </Button>
                      </div>
                    </li>
                  ))
                )}
              </ul>
            </section>
          ))}
        </div>
      )}

      {categoryDraft ? (
        <CategoryModal
          draft={categoryDraft}
          busy={busy}
          onClose={() => setCategoryDraft(null)}
          onSave={(draft) => void saveCategory(draft)}
        />
      ) : null}
      {itemDraft ? (
        <ItemModal
          draft={itemDraft}
          busy={busy}
          onClose={() => setItemDraft(null)}
          onSave={(draft) => void saveItem(draft)}
        />
      ) : null}
    </div>
  );
}
