"use client";

import { KeyRound, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { InlineAlert } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AdminUser } from "@/types/api";

const MIN_LENGTH = 10;

export function PasswordCard({ admin }: { admin: AdminUser | null }) {
  const { notify } = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mismatch = confirm.length > 0 && next !== confirm;
  const tooShort = next.length > 0 && next.length < MIN_LENGTH;
  const canSubmit =
    current.length > 0 && next.length >= MIN_LENGTH && next === confirm && next !== current;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/admins/me/password", {
        current_password: current,
        new_password: next,
      });
      notify("رمز عبور تغییر کرد. سایر نشست های شما بسته شد.", "success");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5">
      <div className="mb-3 flex items-center gap-2">
        <KeyRound size={17} className="text-[#b9a7ff]" aria-hidden />
        <h2 className="text-sm font-semibold">تغییر رمز عبور</h2>
      </div>
      <p className="mb-3 text-[11px] leading-6 text-muted">
        پس از تغییر رمز، همه نشست های دیگر این حساب بسته می شوند و همین صفحه فعال می ماند.
        {admin?.last_password_change_at
          ? ` آخرین تغییر: ${formatDateTime(admin.last_password_change_at)}`
          : ""}
      </p>

      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
        <label className="block text-xs">
          <span className="mb-1 block text-muted">رمز فعلی</span>
          <input
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">رمز جدید (حداقل {MIN_LENGTH} کاراکتر)</span>
          <input
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(event) => setNext(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
          {tooShort ? <span className="field-error">رمز جدید کوتاه است.</span> : null}
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">تکرار رمز جدید</span>
          <input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
          {mismatch ? <span className="field-error">دو رمز یکسان نیستند.</span> : null}
        </label>
        <Button type="submit" size="sm" loading={busy} disabled={!canSubmit}>
          <ShieldCheck size={14} aria-hidden />
          ذخیره رمز جدید
        </Button>
      </form>
    </section>
  );
}
