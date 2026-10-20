"use client";

import clsx from "clsx";
import {
  Archive,
  ArchiveRestore,
  Boxes,
  Check,
  MessageCircle,
  Radio,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { InlineAlert } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { CHANNEL_LABELS } from "@/lib/labels";
import type { Project } from "@/types/api";

function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition",
        checked ? "border-accent/50 bg-accent/70" : "border-line bg-elevated",
        disabled ? "cursor-not-allowed opacity-50" : "",
      )}
    >
      <span
        className={clsx(
          "absolute size-4 rounded-full bg-white transition",
          checked ? "start-1" : "start-6",
        )}
      />
    </button>
  );
}

export function CapabilitiesTab({
  project,
  refreshToken,
  onProjectChanged,
  onDeleted,
}: {
  project: Project;
  refreshToken: number;
  onProjectChanged: () => void;
  onDeleted: () => void;
}) {
  const { notify } = useToast();
  const [features, setFeatures] = useState(
    Object.fromEntries(project.features.map((item) => [item.key, item.enabled])),
  );
  const [channels, setChannels] = useState(
    Object.fromEntries(project.channels.map((item) => [item.channel, item.enabled])),
  );
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  useEffect(() => {
    // A refresh from the parent (after another tab changed something) resets
    // local toggles to the server truth instead of keeping stale state.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing server snapshot
    setFeatures(Object.fromEntries(project.features.map((item) => [item.key, item.enabled])));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing server snapshot
    setChannels(Object.fromEntries(project.channels.map((item) => [item.channel, item.enabled])));
  }, [project, refreshToken]);

  async function saveFeatures(next: Record<string, boolean>, key: string) {
    setBusyKey(`feature:${key}`);
    setError(null);
    try {
      await api.put(`/projects/${project.id}/features`, { features: next });
      notify("قابلیت های پروژه به روز شد.", "success");
      onProjectChanged();
    } catch (err) {
      setError(errorMessage(err));
      setFeatures(Object.fromEntries(project.features.map((item) => [item.key, item.enabled])));
    } finally {
      setBusyKey(null);
    }
  }

  async function saveChannel(channel: string, enabled: boolean) {
    setBusyKey(`channel:${channel}`);
    setError(null);
    try {
      await api.put(`/projects/${project.id}/channels/${channel}`, { enabled });
      notify(
        enabled
          ? `کانال ${CHANNEL_LABELS[channel] ?? channel} برای این پروژه فعال شد.`
          : `کانال ${CHANNEL_LABELS[channel] ?? channel} غیرفعال شد.`,
        "success",
      );
      onProjectChanged();
    } catch (err) {
      setError(errorMessage(err));
      setChannels(Object.fromEntries(project.channels.map((item) => [item.channel, item.enabled])));
    } finally {
      setBusyKey(null);
    }
  }

  async function archive() {
    setBusyKey("archive");
    try {
      await api.post(`/projects/${project.id}/archive`);
      notify("پروژه بایگانی شد و ارسال های آن متوقف شد.", "success");
      onProjectChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyKey(null);
      setArchiveOpen(false);
    }
  }

  async function restore() {
    setBusyKey("restore");
    try {
      await api.post(`/projects/${project.id}/restore`);
      notify("پروژه از بایگانی خارج شد.", "success");
      onProjectChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyKey(null);
    }
  }

  async function destroy() {
    setDeleteBusy(true);
    try {
      await api.del(
        `/projects/${project.id}?confirm=${encodeURIComponent(project.name)}`,
      );
      notify("پروژه برای همیشه حذف شد.", "success");
      onDeleted();
    } catch (err) {
      setError(errorMessage(err));
      setDeleteOpen(false);
    } finally {
      setDeleteBusy(false);
    }
  }

  const archived = Boolean(project.archived_at);

  return (
    <div className="space-y-4">
      {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
      {archived ? (
        <InlineAlert tone="warning">
          این پروژه بایگانی شده است. ربات و ارسال های آن متوقف است و تیکت جدید نمی پذیرد.
          بازگردانی، پروژه را دوباره فعال می کند.
        </InlineAlert>
      ) : null}

      <section className="panel p-5">
        <div className="mb-1 flex items-center gap-2">
          <Boxes size={17} className="text-[#b9a7ff]" aria-hidden />
          <h2 className="text-sm font-semibold">قابلیت های این پروژه</h2>
        </div>
        <p className="mb-4 text-[11px] leading-6 text-muted">
          هر قابلیت یک دکمه در منوی ربات این کارفرما است. قابلیت های جدید از طریق رجیستری
          افزونه ها اضافه می شوند و بدون تغییر پنل در همین فهرست دیده می شوند.
        </p>
        <ul className="space-y-2">
          {project.features.map((feature) => (
            <li
              key={feature.key}
              className="flex items-start justify-between gap-4 rounded-xl border border-line-soft bg-elevated/30 px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-medium">{feature.label}</span>
                  {feature.implemented ? (
                    <Badge tone="success">
                      <Check size={10} aria-hidden /> آماده
                    </Badge>
                  ) : (
                    <Badge tone="warning">به زودی</Badge>
                  )}
                </div>
                <p className="mt-1 text-[10px] leading-6 text-muted">
                  {feature.description ||
                    (feature.implemented
                      ? "این قابلیت به صورت واقعی در ربات فعال می شود."
                      : "با فعال بودن، ربات پیام «به زودی» نشان می دهد.")}
                </p>
              </div>
              <Toggle
                label={`فعال سازی ${feature.label}`}
                checked={features[feature.key] ?? false}
                disabled={busyKey === `feature:${feature.key}`}
                onChange={(value) => {
                  const next = { ...features, [feature.key]: value };
                  setFeatures(next);
                  void saveFeatures(next, feature.key);
                }}
              />
            </li>
          ))}
        </ul>
      </section>

      <section className="panel p-5">
        <div className="mb-1 flex items-center gap-2">
          <Radio size={17} className="text-[#b9a7ff]" aria-hidden />
          <h2 className="text-sm font-semibold">کانال های ارسال</h2>
        </div>
        <p className="mb-4 text-[11px] leading-6 text-muted">
          حساب های سرویس دهنده به صورت مرکزی روی سرور تنظیم می شوند؛ اینجا فقط مشخص می کنید
          این پروژه از کدام کانال ها استفاده کند. کانالی که روی سرور تنظیم نشده باشد قابل
          فعال سازی نیست.
        </p>
        <ul className="space-y-2">
          {project.channels.map((channel) => (
            <li
              key={channel.channel}
              className="flex items-start justify-between gap-4 rounded-xl border border-line-soft bg-elevated/30 px-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs font-medium">
                    {channel.label || CHANNEL_LABELS[channel.channel] || channel.channel}
                  </span>
                  {channel.beta ? <Badge tone="info">بتا</Badge> : null}
                  {channel.configured ? (
                    <Badge tone="success">روی سرور تنظیم شده</Badge>
                  ) : (
                    <Badge tone="neutral">تنظیم نشده</Badge>
                  )}
                  <Badge tone="neutral">
                    {channel.mode === "mock" ? "شبیه سازی" : channel.mode}
                  </Badge>
                </div>
                <p className="mt-1 text-[10px] leading-6 text-muted">
                  {channel.configured
                    ? `فرمت مقصد: ${channel.recipient_hint}`
                    : "برای فعال کردن، کلیدهای سرویس را در متغیرهای محیطی سرور تنظیم کنید."}
                </p>
              </div>
              <Toggle
                label={`فعال سازی ${channel.channel}`}
                checked={channels[channel.channel] ?? false}
                disabled={!channel.configured || busyKey === `channel:${channel.channel}`}
                onChange={(value) => {
                  setChannels((previous) => ({ ...previous, [channel.channel]: value }));
                  void saveChannel(channel.channel, value);
                }}
              />
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[10px] leading-6 text-muted">
          گیرنده های بله، ایتا و پیامک برای هر کارفرما در بخش «کاربران مجاز» ثبت می شوند؛
          تلگرام از هویت خود ربات استفاده می کند.
        </p>
      </section>

      <section className="panel border border-danger/20 p-5">
        <div className="mb-1 flex items-center gap-2">
          <TriangleAlert size={17} className="text-danger" aria-hidden />
          <h2 className="text-sm font-semibold">بایگانی و حذف</h2>
        </div>
        <p className="mb-4 text-[11px] leading-6 text-muted">
          بایگانی تاریخچه را نگه می دارد و فقط عملیات را متوقف می کند. حذف قطعی اطلاعات
          پروژه، لایسنس، اعضا و تیکت ها را پاک می کند و قابل بازگشت نیست.
        </p>
        <div className="flex flex-wrap gap-2">
          {archived ? (
            <Button variant="secondary" size="sm" onClick={() => void restore()} loading={busyKey === "restore"}>
              <ArchiveRestore size={14} aria-hidden />
              خروج از بایگانی
            </Button>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setArchiveOpen(true)}
              loading={busyKey === "archive"}
            >
              <Archive size={14} aria-hidden />
              بایگانی کردن پروژه
            </Button>
          )}
          <Button
            variant="danger"
            size="sm"
            onClick={() => setDeleteOpen(true)}
            disabled={!archived}
            title={archived ? undefined : "برای حذف قطعی، ابتدا پروژه را بایگانی کنید."}
          >
            <Trash2 size={14} aria-hidden />
            حذف قطعی
          </Button>
        </div>
        {!archived ? (
          <p className="mt-2 text-[10px] leading-6 text-muted">
            برای حذف قطعی، ابتدا پروژه را بایگانی کنید. این مرحله عمداً جدا شده تا حذف
            تصادفی یک پروژه فعال ممکن نباشد.
          </p>
        ) : null}
      </section>

      <section className="panel p-5">
        <div className="mb-2 flex items-center gap-2">
          <MessageCircle size={16} className="text-[#b9a7ff]" aria-hidden />
          <h2 className="text-sm font-semibold">گفتگوی کارفرما</h2>
        </div>
        <p className="text-[11px] leading-6 text-muted">
          تیکت های این پروژه در تب «پشتیبانی» همین صفحه و صفحه «تیکت ها» قابل مشاهده و
          پاسخ هستند.
        </p>
      </section>

      <ConfirmDialog
        open={archiveOpen}
        onClose={() => setArchiveOpen(false)}
        onConfirm={() => void archive()}
        loading={busyKey === "archive"}
        tone="danger"
        title="بایگانی پروژه"
        message="با بایگانی، ربات و ارسال های پروژه متوقف می شوند و تیکت جدید پذیرفته نمی شود. داده ها حفظ می شوند."
        confirmLabel="بایگانی کن"
      />

      <DeleteProjectDialog
        open={deleteOpen}
        project={project}
        loading={deleteBusy}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => void destroy()}
      />
    </div>
  );
}

function DeleteProjectDialog({
  open,
  project,
  loading,
  onClose,
  onConfirm,
}: {
  open: boolean;
  project: Project;
  loading: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [value, setValue] = useState("");
  const matches = value.trim() === project.name;
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-project-title"
        className="w-full max-w-md rounded-2xl border border-danger/30 bg-surface p-5 shadow-2xl"
      >
        <h2 id="delete-project-title" className="text-sm font-semibold">
          حذف قطعی «{project.name}»
        </h2>
        <p className="mt-2 text-[11px] leading-6 text-muted">
          این عملیات قابل بازگشت نیست. برای تایید، نام پروژه را دقیقا بنویسید.
        </p>
        <input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="mt-3 h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          placeholder={project.name}
          aria-label="نام پروژه برای تایید حذف"
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose} disabled={loading}>
            انصراف
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={onConfirm}
            loading={loading}
            disabled={!matches}
          >
            <Trash2 size={13} aria-hidden />
            حذف قطعی
          </Button>
        </div>
      </div>
    </div>
  );
}
