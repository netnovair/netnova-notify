"use client";

import { KeyRound, Plus, UserCog, UserX } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime, formatRelative } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { AdminUser } from "@/types/api";

type TemporaryPassword = {
  admin_id: string;
  temporary_password: string;
  message: string;
};

export function AdminsCard({ currentAdminId }: { currentAdminId: string | null }) {
  const { notify } = useToast();
  const admins = useApiData<AdminUser[]>(
    (signal) => api.get<AdminUser[]>("/admins", signal),
    [],
  );
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [temporary, setTemporary] = useState<TemporaryPassword | null>(null);

  async function toggleActive(admin: AdminUser) {
    setBusyId(admin.id);
    setError(null);
    try {
      await api.patch(`/admins/${admin.id}`, { is_active: !admin.is_active });
      notify(
        admin.is_active ? "حساب مدیر غیرفعال شد." : "حساب مدیر فعال شد.",
        "success",
      );
      admins.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  async function resetPassword(admin: AdminUser) {
    const confirmed = window.confirm(
      `رمز عبور «${admin.display_name}» بازنشانی شود؟ تمام نشست های او بسته می شود.`,
    );
    if (!confirmed) return;
    setBusyId(admin.id);
    setError(null);
    try {
      const result = await api.post<TemporaryPassword>(`/admins/${admin.id}/reset-password`, {
        confirm_email: admin.email,
      });
      setTemporary(result);
      admins.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <UserCog size={17} className="text-[#b9a7ff]" aria-hidden />
        <h2 className="text-sm font-semibold">مدیران اپلیکیشن</h2>
        <Button size="sm" className="ms-auto" onClick={() => setCreateOpen(true)}>
          <Plus size={13} aria-hidden />
          مدیر جدید
        </Button>
      </div>
      <p className="mb-3 text-[11px] leading-6 text-muted">
        هر مدیر با ایمیل و رمز خودش وارد می شود. غیرفعال کردن، دسترسی را فورا قطع می کند و
        نشست های فعال را می بندد. مدیر آخر را نمی توان غیرفعال کرد.
      </p>

      {error ? (
        <div className="mb-3">
          <InlineAlert tone="danger">{error}</InlineAlert>
        </div>
      ) : null}

      {admins.error && !admins.data ? (
        <ErrorState message={admins.error} onRetry={admins.reload} compact />
      ) : admins.loading && !admins.data ? (
        <SkeletonRows rows={3} />
      ) : (
        <ul className="divide-y divide-line-soft">
          {(admins.data ?? []).map((admin) => {
            const isSelf = admin.id === currentAdminId;
            return (
              <li key={admin.id} className="flex flex-wrap items-center gap-2 py-2.5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-medium">{admin.display_name}</span>
                    {isSelf ? <Badge tone="accent">شما</Badge> : null}
                    {admin.is_active ? (
                      <Badge tone="success">فعال</Badge>
                    ) : (
                      <Badge tone="neutral">غیرفعال</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-[10px] text-muted" dir="ltr">
                    {admin.email}
                  </p>
                  <p className="text-[10px] text-muted">
                    آخرین ورود:{" "}
                    {admin.last_login_at ? formatRelative(admin.last_login_at) : "بدون ورود"}
                    {admin.last_password_change_at
                      ? ` · تغییر رمز: ${formatDateTime(admin.last_password_change_at)}`
                      : ""}
                  </p>
                </div>
                <div className="ms-auto flex items-center gap-1.5">
                  {!isSelf ? (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => void resetPassword(admin)}
                        loading={busyId === admin.id}
                        title="بازنشانی رمز و بستن نشست ها"
                      >
                        <KeyRound size={13} aria-hidden />
                        بازنشانی رمز
                      </Button>
                      <Button
                        size="sm"
                        variant={admin.is_active ? "danger" : "secondary"}
                        onClick={() => void toggleActive(admin)}
                        loading={busyId === admin.id}
                      >
                        <UserX size={13} aria-hidden />
                        {admin.is_active ? "غیرفعال" : "فعال"}
                      </Button>
                    </>
                  ) : (
                    <span className="text-[10px] text-muted">
                      برای تغییر رمز خودتان از بخش بالا استفاده کنید
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {createOpen ? (
        <CreateAdminModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            admins.reload();
            notify("مدیر جدید ساخته شد.", "success");
          }}
        />
      ) : null}

      {temporary ? (
        <Modal
          open
          onClose={() => setTemporary(null)}
          title="رمز موقت ساخته شد"
          description="این رمز فقط یک بار نمایش داده می شود. آن را از مسیر امن به مدیر برسانید."
          size="sm"
          footer={
            <Button size="sm" onClick={() => setTemporary(null)}>
              متوجه شدم
            </Button>
          }
        >
          <p
            dir="ltr"
            className="select-all rounded-lg border border-line bg-bg/70 px-3 py-2 text-center font-mono text-sm tracking-wider"
          >
            {temporary.temporary_password}
          </p>
          <p className="mt-3 text-[11px] leading-6 text-muted">{temporary.message}</p>
        </Modal>
      ) : null}
    </section>
  );
}

function CreateAdminModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (admin: AdminUser) => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<AdminUser>("/admins", {
        email,
        display_name: displayName,
        password,
      });
      onCreated(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="مدیر جدید"
      description="رمز اولیه را به صورت امن به مدیر بدهید تا بعدا تغییرش دهد."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            انصراف
          </Button>
          <Button
            onClick={() => void submit()}
            loading={busy}
            disabled={!email.includes("@") || displayName.trim().length < 2 || password.length < 10}
          >
            <Plus size={14} aria-hidden />
            ساخت مدیر
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
        <label className="block text-xs">
          <span className="mb-1 block text-muted">ایمیل</span>
          <input
            dir="ltr"
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">نام نمایشی</span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">رمز اولیه (حداقل ۱۰ کاراکتر)</span>
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
        </label>
      </div>
    </Modal>
  );
}
