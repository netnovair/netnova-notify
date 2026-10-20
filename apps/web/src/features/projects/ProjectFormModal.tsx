"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { api, errorMessage } from "@/lib/api";
import { FEATURE_LABELS } from "@/lib/labels";
import { projectSchema, type ProjectValues } from "@/lib/validation";
import type { FeatureKey, Project, ProjectCreated } from "@/types/api";

const FEATURE_ORDER: FeatureKey[] = [
  "announcements",
  "financial",
  "support",
  "performance",
  "progress",
];

const FEATURE_HELP: Record<string, string> = {
  announcements: "نمایش آخرین اطلاعیه های ارسال شده",
  financial: "نمایش پرداخت های باز و مبالغ",
  support: "ثبت و پیگیری تیکت پشتیبانی از داخل ربات",
  performance: "به زودی",
  progress: "به زودی",
};

function defaultsFrom(project?: Project): ProjectValues {
  return {
    name: project?.name ?? "",
    client_name: project?.client_name ?? "",
    slug: project?.slug ?? "",
    description: project?.description ?? "",
    features: Object.fromEntries(
      FEATURE_ORDER.map((key) => [
        key,
        project ? (project.features.find((item) => item.key === key)?.enabled ?? true) : true,
      ]),
    ) as Record<string, boolean | undefined>,
  };
}

export function ProjectFormModal({
  open,
  onClose,
  project,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  project?: Project;
  onSaved: (project: ProjectCreated) => void;
}) {
  const isEdit = Boolean(project);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ProjectValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: defaultsFrom(project),
  });

  const features = watch("features") ?? {};

  async function onSubmit(values: ProjectValues) {
    setServerError(null);
    const payload = {
      name: values.name,
      client_name: values.client_name,
      description: values.description?.trim() ? values.description : null,
      features: values.features,
      ...(values.slug?.trim() ? { slug: values.slug.trim() } : {}),
    };
    try {
      if (isEdit && project) {
        const updated = await api.patch<Project>(`/projects/${project.id}`, payload);
        onSaved({ ...updated, license_code: null });
      } else {
        const created = await api.post<ProjectCreated>("/projects", payload);
        onSaved(created);
      }
      onClose();
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "ویرایش پروژه" : "پروژه جدید"}
      description={
        isEdit
          ? "تغییرات قابلیت ها بلافاصله در منوی تلگرام کارفرما اعمال می شود."
          : "پس از ایجاد، لایسنس اختصاصی پروژه به صورت خودکار صادر می شود."
      }
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            انصراف
          </Button>
          <Button onClick={() => void handleSubmit(onSubmit)()} loading={isSubmitting}>
            {isEdit ? "ذخیره تغییرات" : "ایجاد پروژه"}
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

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="project-name" className="field-label">
              نام پروژه
            </label>
            <input
              id="project-name"
              className="field-input"
              placeholder="مثلا فروشگاه آنلاین آرمان"
              aria-invalid={errors.name ? "true" : undefined}
              {...register("name")}
            />
            {errors.name ? <p className="field-error">{errors.name.message}</p> : null}
          </div>
          <div>
            <label htmlFor="project-client" className="field-label">
              نام کارفرما
            </label>
            <input
              id="project-client"
              className="field-input"
              placeholder="مثلا آرمان تجارت"
              aria-invalid={errors.client_name ? "true" : undefined}
              {...register("client_name")}
            />
            {errors.client_name ? (
              <p className="field-error">{errors.client_name.message}</p>
            ) : null}
          </div>
        </div>

        {!isEdit ? (
          <div>
            <label htmlFor="project-slug" className="field-label">
              شناسه انگلیسی <span className="font-normal text-muted">(اختیاری)</span>
            </label>
            <input
              id="project-slug"
              dir="ltr"
              className="field-input text-start"
              placeholder="arman-shop"
              aria-invalid={errors.slug ? "true" : undefined}
              {...register("slug")}
            />
            {errors.slug ? <p className="field-error">{errors.slug.message}</p> : null}
            <p className="field-hint">در صورت خالی گذاشتن، شناسه یکتا به صورت خودکار ساخته می شود.</p>
          </div>
        ) : null}

        <div>
          <label htmlFor="project-description" className="field-label">
            توضیحات <span className="font-normal text-muted">(اختیاری)</span>
          </label>
          <textarea
            id="project-description"
            rows={3}
            className="field-input resize-y"
            placeholder="توضیح کوتاه درباره دامنه پروژه"
            {...register("description")}
          />
          {errors.description ? (
            <p className="field-error">{errors.description.message}</p>
          ) : null}
        </div>

        <fieldset className="rounded-xl border border-line bg-elevated/40 p-3">
          <legend className="px-1 text-xs text-muted">قابلیت های منوی کارفرما</legend>
          <div className="mt-1 divide-y divide-line-soft">
            {FEATURE_ORDER.map((key) => {
              const enabled = Boolean((features as Record<string, boolean | undefined>)?.[key]);
              return (
                <label
                  key={key}
                  className="flex cursor-pointer items-center justify-between gap-3 py-2.5"
                >
                  <span>
                    <span className="block text-sm text-ink">{FEATURE_LABELS[key]}</span>
                    <span className="block text-[11px] text-muted">{FEATURE_HELP[key]}</span>
                  </span>
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={enabled}
                    onChange={(event) =>
                      setValue(
                        `features.${key}` as "features.announcements",
                        event.target.checked,
                        { shouldDirty: true },
                      )
                    }
                  />
                  <span
                    aria-hidden
                    className={`relative h-6 w-11 shrink-0 rounded-full border transition ${
                      enabled ? "border-accent/60 bg-accent/80" : "border-line bg-bg"
                    } after:absolute after:top-0.5 after:h-4.5 after:w-4.5 after:rounded-full after:bg-white after:transition-all ${
                      enabled ? "after:start-5.5" : "after:start-0.5"
                    }`}
                  />
                </label>
              );
            })}
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
