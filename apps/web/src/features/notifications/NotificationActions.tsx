"use client";

import { RotateCcw, Send, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import type { Notification, NotificationListItem, NotificationStatus } from "@/types/api";

export function notificationCapabilities(status: NotificationStatus) {
  return {
    canSendNow: status === "queued",
    canCancel: status === "queued" || status === "retry_wait",
    canRetry: status === "failed",
  };
}

export function NotificationActions({
  notification,
  onChanged,
  compact = false,
}: {
  notification: Notification | NotificationListItem;
  onChanged: () => void;
  compact?: boolean;
}) {
  const { notify } = useToast();
  const [pending, setPending] = useState<null | "send" | "cancel" | "retry">(null);
  const [busy, setBusy] = useState(false);
  const caps = notificationCapabilities(notification.status);

  async function run(action: "send" | "cancel") {
    setBusy(true);
    try {
      await api.post(`/notifications/${notification.id}/${action}`);
      notify(
        action === "cancel" ? "اطلاعیه لغو شد." : "درخواست ارسال ثبت شد.",
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

  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        {caps.canSendNow ? (
          <Button variant="secondary" size="sm" onClick={() => setPending("send")}>
            <Send size={13} aria-hidden />
            ارسال فوری
          </Button>
        ) : null}
        {caps.canRetry ? (
          <Button variant="secondary" size="sm" onClick={() => setPending("retry")}>
            <RotateCcw size={13} aria-hidden />
            تلاش دوباره
          </Button>
        ) : null}
        {caps.canCancel ? (
          <Button variant="ghost" size="sm" onClick={() => setPending("cancel")}>
            <XCircle size={13} aria-hidden />
            {compact ? "لغو" : "لغو ارسال"}
          </Button>
        ) : null}
      </div>

      <ConfirmDialog
        open={pending === "send"}
        onClose={() => setPending(null)}
        onConfirm={() => run("send")}
        loading={busy}
        title="ارسال فوری اطلاعیه"
        message="ارسال زمان بندی شده لغو و پیام در اولین فرصت توسط Worker ارسال می شود. ادامه می دهید؟"
        confirmLabel="ارسال فوری"
      />
      <ConfirmDialog
        open={pending === "retry"}
        onClose={() => setPending(null)}
        onConfirm={() => run("send")}
        loading={busy}
        title="تلاش دوباره برای ارسال"
        message="یک کار جدید در صف قرار می گیرد. اگر خطای قبلی موقت بوده، پیام دوباره ارسال می شود. ادامه می دهید؟"
        confirmLabel="تلاش دوباره"
      />
      <ConfirmDialog
        open={pending === "cancel"}
        onClose={() => setPending(null)}
        onConfirm={() => run("cancel")}
        loading={busy}
        tone="danger"
        title="لغو اطلاعیه"
        message="کار ارسال از صف حذف می شود. اگر پیام قبلا ارسال شده باشد، این عملیات آن را حذف نمی کند."
        confirmLabel="لغو اطلاعیه"
      />
    </>
  );
}
