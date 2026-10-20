"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { fromDateTimeInput, toDateInput } from "@/lib/format";
import { licenseSchema, type LicenseValues } from "@/lib/validation";
import type { LicenseCreated, ProjectListItem } from "@/types/api";

function defaultExpiry(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() + 1);
  return toDateInput(date.toISOString());
}

export function LicenseIssueModal({
  open,
  onClose,
  projects,
  fixedProjectId,
  onIssued,
}: {
  open: boolean;
  onClose: () => void;
  projects: ProjectListItem[];
  fixedProjectId?: string;
  onIssued: (license: LicenseCreated) => void;
}) {
  const { notify } = useToast();
  const [projectId, setProjectId] = useState(fixedProjectId ?? projects[0]?.id ?? "");
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LicenseValues>({
    resolver: zodResolver(licenseSchema),
    defaultValues: { expires_at: defaultExpiry() },
  });

  async function onSubmit(values: LicenseValues) {
    if (!projectId) {
      setServerError("ابتدا پروژه را انتخاب کنید.");
      return;
    }
    setServerError(null);
    try {
      const expiresAt = values.expires_at
        ? fromDateTimeInput(`${values.expires_at}T23:59`)
        : null;
      const license = await api.post<LicenseCreated>(`/projects/${projectId}/licenses`, {
        expires_at: expiresAt,
      });
      notify("لایسنس جدید صادر شد. کد قبلی لغو شد.", "success");
      onIssued(license);
      onClose();
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="صدور لایسنس"
      description="برای هر پروژه فقط یک لایسنس فعال یا در انتظار فعال سازی نگهداری می شود."
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            انصراف
          </Button>
          <Button onClick={() => void handleSubmit(onSubmit)()} loading={isSubmitting}>
            صدور لایسنس
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {serverError ? (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger/[0.07] px-3 py-2 text-xs leading-6 text-[#ffb4b4]">
            {serverError}
          </p>
        ) : null}

        <div>
          <label htmlFor="license-project" className="field-label">
            پروژه
          </label>
          {fixedProjectId ? (
            <p className="rounded-xl border border-line bg-elevated px-3.5 py-2.5 text-sm">
              {projects.find((project) => project.id === fixedProjectId)?.name ?? "پروژه جاری"}
            </p>
          ) : (
            <select
              id="license-project"
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
          )}
        </div>

        <div>
          <label htmlFor="license-expiry" className="field-label">
            تاریخ انقضا
          </label>
          <input
            id="license-expiry"
            type="date"
            className="field-input"
            min={new Date().toISOString().slice(0, 10)}
            aria-invalid={errors.expires_at ? "true" : undefined}
            {...register("expires_at")}
          />
          {errors.expires_at ? <p className="field-error">{errors.expires_at.message}</p> : null}
          <p className="field-hint">
            خالی گذاشتن این فیلد به معنی لایسنس بدون تاریخ انقضاست. پیش فرض یک سال است.
          </p>
        </div>

        <div className="flex items-start gap-2 rounded-xl border border-warning/25 bg-warning/[0.05] px-3 py-2.5 text-[11px] leading-6 text-[#f5d992]">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden />
          صدور لایسنس جدید، لایسنس فعال قبلی همین پروژه را لغو می کند. کارفرمای تاییدشده
          متصل باقی می ماند.
        </div>
      </form>
    </Modal>
  );
}
