"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarClock, Send, Sparkles } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { TelegramHtml } from "@/features/accounting/TelegramHtml";
import { RichTextEditor } from "@/features/rich-text/RichTextEditor";
import { api, errorMessage } from "@/lib/api";
import { fromDateTimeInput, toDateTimeInput } from "@/lib/format";
import { NOTIFICATION_TYPE } from "@/lib/labels";
import { notificationSchema, type NotificationValues } from "@/lib/validation";
import type { Notification, ProjectChannel } from "@/types/api";

function defaultSchedule(): string {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  return toDateTimeInput(date.toISOString());
}

export function NotificationFormModal({
  open,
  onClose,
  project,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  project: { id: string; name: string; channels?: ProjectChannel[] } | null;
  onCreated: (notification: Notification) => void;
}) {
  const { notify } = useToast();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<NotificationValues>({
    resolver: zodResolver(notificationSchema),
    defaultValues: {
      title: "",
      body: "",
      type: "announcement",
      scheduling: "now",
      scheduled_at: defaultSchedule(),
    },
  });

  const title = watch("title");
  const body = watch("body");
  const type = watch("type");
  const scheduling = watch("scheduling");
  const scheduledAt = watch("scheduled_at");
  const enabledChannels = (project?.channels ?? []).filter(
    (channel) => channel.enabled && channel.configured,
  );
  const [selectedChannels, setSelectedChannels] = useState<string[]>(["telegram"]);

  async function onSubmit(values: NotificationValues) {
    if (!project) return;
    setServerError(null);
    try {
      const created = await api.post<Notification>(`/projects/${project.id}/notifications`, {
        type: values.type,
        title: values.title,
        body: values.body,
        scheduled_at:
          values.scheduling === "later" && values.scheduled_at
            ? fromDateTimeInput(values.scheduled_at)
            : null,
        channels: selectedChannels.length > 0 ? selectedChannels : ["telegram"],
      });
      notify(
        values.scheduling === "later"
          ? "اطلاعیه زمان بندی شد و در صف ارسال قرار گرفت."
          : "اطلاعیه ثبت شد و در صف ارسال قرار گرفت.",
        "success",
      );
      onCreated(created);
      onClose();
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="اطلاعیه جدید"
      description={
        project
          ? `گیرنده: کارفرمای تاییدشده پروژه «${project.name}»`
          : "ابتدا پروژه را انتخاب کنید."
      }
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            انصراف
          </Button>
          <Button
            onClick={() => void handleSubmit(onSubmit)()}
            loading={isSubmitting}
            disabled={!project}
          >
            <Send size={15} aria-hidden />
            {scheduling === "later" ? "ثبت و زمان بندی" : "ثبت و ارسال"}
          </Button>
        </>
      }
    >
      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          {serverError ? (
            <p
              role="alert"
              className="rounded-lg border border-danger/30 bg-danger/[0.07] px-3 py-2 text-xs leading-6 text-[#ffb4b4]"
            >
              {serverError}
            </p>
          ) : null}

          <div>
            <label htmlFor="notification-type" className="field-label">
              نوع اطلاعیه
            </label>
            <select id="notification-type" className="field-input" {...register("type")}>
              <option value="announcement">اطلاعیه عمومی</option>
              <option value="financial">اطلاعیه مالی</option>
              <option value="system">اطلاعیه سیستمی</option>
            </select>
          </div>

          <div>
            <label htmlFor="notification-title" className="field-label">
              عنوان
            </label>
            <input
              id="notification-title"
              className="field-input"
              placeholder="مثلا تحویل نسخه اول طراحی"
              maxLength={200}
              aria-invalid={errors.title ? "true" : undefined}
              {...register("title")}
            />
            {errors.title ? <p className="field-error">{errors.title.message}</p> : null}
          </div>

          <div>
            <span className="field-label">متن پیام</span>
            <Controller
              control={control}
              name="body"
              render={({ field }) => (
                <RichTextEditor
                  id="notification-body"
                  value={field.value ?? ""}
                  onChange={field.onChange}
                  maxLength={3500}
                  placeholder="متن پیامی که برای کارفرما در تلگرام ارسال می شود."
                  error={errors.body?.message}
                  showPreview={false}
                />
              )}
            />
          </div>

          <fieldset>
            <legend className="field-label">زمان ارسال</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              <label
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition ${
                  scheduling === "now"
                    ? "border-accent/60 bg-accent/10 text-ink"
                    : "border-line bg-elevated text-muted hover:border-line"
                }`}
              >
                <input type="radio" value="now" className="accent-[#7c5cff]" {...register("scheduling")} />
                <Send size={15} aria-hidden />
                ارسال فوری
              </label>
              <label
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition ${
                  scheduling === "later"
                    ? "border-accent/60 bg-accent/10 text-ink"
                    : "border-line bg-elevated text-muted"
                }`}
              >
                <input type="radio" value="later" className="accent-[#7c5cff]" {...register("scheduling")} />
                <CalendarClock size={15} aria-hidden />
                زمان بندی
              </label>
            </div>
            {scheduling === "later" ? (
              <div className="mt-3">
                <input
                  type="datetime-local"
                  className="field-input"
                  aria-label="زمان ارسال"
                  aria-invalid={errors.scheduled_at ? "true" : undefined}
                  {...register("scheduled_at")}
                />
                {errors.scheduled_at ? (
                  <p className="field-error">{errors.scheduled_at.message}</p>
                ) : null}
                <p className="field-hint">
                  زمان بر اساس منطقه زمانی مرورگر شما ذخیره می شود. ارسال توسط Worker و
                  پس از رسیدن زمان انجام می شود.
                </p>
              </div>
            ) : (
              <p className="field-hint">
                اطلاعیه در صف پایدار قرار می گیرد و Worker آن را برای کارفرمای تاییدشده
                ارسال می کند.
              </p>
            )}
          </fieldset>
        </form>

        <div>
          <div className="mb-2 flex items-center gap-1.5 text-[11px] text-muted">
            <Sparkles size={13} aria-hidden />
            پیش نمایش تقریبی پیام تلگرام
          </div>
          <div className="rounded-2xl border border-line bg-[#0b1324] p-3">
            <div className="rounded-xl rounded-tr-sm bg-[#17223d] p-3.5 text-[13px] leading-7 shadow-sm">
              <p className="font-semibold text-[#c9bcff]">{project?.name ?? "نام پروژه"}</p>
              <p className="text-[11px] italic text-muted">
                {NOTIFICATION_TYPE[type] ?? "اطلاعیه"}
              </p>
              <p className="mt-2 font-semibold text-ink">{title || "عنوان اطلاعیه"}</p>
              <div className="mt-1 whitespace-pre-wrap break-words text-[#dfe5f5]">
                {body ? (
                  <TelegramHtml html={body} />
                ) : (
                  "متن پیام شما اینجا نمایش داده می شود."
                )}
              </div>
              <p className="mt-2 text-[10px] italic text-muted">NetNova Notify</p>
            </div>
            {scheduledAt && scheduling === "later" ? (
              <p className="mt-2 text-center text-[10px] text-muted">
                زمان بندی: {scheduledAt.replace("T", " ")}
              </p>
            ) : null}
          </div>
          <p className="mt-2 text-[10px] leading-6 text-muted">
            فقط تگ های رسمی تلگرام (درشت، کج، زیرخط، خط خورده، code، pre، blockquote و
            لینک http/https) پشتیبانی می شوند؛ سایر تگ ها به صورت متن ساده ارسال می شوند.
            متن داخل code در تلگرام قابل کپی است.
          </p>
        </div>
      </div>
    </Modal>
  );
}
