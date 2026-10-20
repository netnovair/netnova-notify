"use client";

import { AlertTriangle, KeyRound } from "lucide-react";

import { CopyButton } from "@/components/ui/CopyButton";
import { Modal } from "@/components/ui/Modal";

export function LicenseRevealModal({
  open,
  onClose,
  code,
  projectName,
  title = "کد لایسنس صادر شد",
  warning,
}: {
  open: boolean;
  onClose: () => void;
  code: string | null;
  projectName?: string;
  title?: string;
  warning?: string;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={
        projectName ? `این کد مخصوص پروژه «${projectName}» است.` : undefined
      }
      footer={
        <button
          type="button"
          onClick={onClose}
          className="h-11 rounded-xl bg-accent px-5 text-sm font-medium text-white transition hover:bg-accent-strong"
        >
          متوجه شدم
        </button>
      }
    >
      <div className="space-y-5">
        <div className="flex items-start gap-3 rounded-xl border border-warning/30 bg-warning/[0.06] px-4 py-3 text-xs leading-7 text-[#f5d992]">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
          <p>
            {warning ??
              "این کد در پایگاه داده رمزنگاری شده ذخیره می شود و فقط مدیر می تواند آن را ببیند. آن را از طریق کانال امن به کارفرما برسانید."}
          </p>
        </div>

        <div className="rounded-xl border border-line bg-elevated p-4">
          <div className="mb-2 flex items-center gap-2 text-xs text-muted">
            <KeyRound size={14} aria-hidden />
            کد لایسنس
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <code
              dir="ltr"
              className="break-all rounded-lg bg-bg/70 px-3 py-2 text-center text-base tracking-[0.12em] text-ink sm:text-start"
            >
              {code ?? "—"}
            </code>
            <CopyButton
              value={code ?? ""}
              label="کپی کد"
              successMessage="کد لایسنس کپی شد."
              disabled={!code}
              variant="primary"
              size="sm"
            />
          </div>
        </div>

        <ol className="space-y-2 text-xs leading-7 text-muted">
          <li>۱. کارفرما در تلگرام ربات مرکزی نت نووا را باز می کند و Start را می زند.</li>
          <li>۲. کد لایسنس را به ربات ارسال می کند.</li>
          <li>۳. پس از تایید مدیر در تب «کاربران مجاز»، منوی پروژه برای او فعال می شود.</li>
        </ol>
      </div>
    </Modal>
  );
}
