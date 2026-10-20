"use client";

import { Check, Copy, MessageCircle, ShieldCheck, UserX } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { ConfirmDialog } from "@/components/ui/Modal";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { MemberStatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { MemberChannels } from "@/features/projects/MemberChannels";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime, formatTelegramHandle } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { Member, Project } from "@/types/api";

export function MembersTab({
  project,
  refreshToken,
  onProjectChanged,
}: {
  project: Project;
  refreshToken: number;
  onProjectChanged: () => void;
}) {
  const { notify } = useToast();
  const [approveTarget, setApproveTarget] = useState<Member | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<Member | null>(null);
  const [busy, setBusy] = useState(false);

  const members = useApiData<Member[]>(
    (signal) => api.get<Member[]>(`/projects/${project.id}/members`, signal),
    [project.id, refreshToken],
  );

  const pending = (members.data ?? []).filter((member) => member.status === "pending_approval");
  const active = (members.data ?? []).filter((member) => member.status === "active");
  const revoked = (members.data ?? []).filter((member) => member.status === "revoked");

  async function approve() {
    if (!approveTarget) return;
    setBusy(true);
    try {
      await api.post(`/projects/${project.id}/members/${approveTarget.id}/approve`);
      notify("اتصال کارفرما تایید شد و پیام خوش آمدگویی در صف ارسال قرار گرفت.", "success");
      setApproveTarget(null);
      members.reload();
      onProjectChanged();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (!revokeTarget) return;
    setBusy(true);
    try {
      await api.post(`/projects/${project.id}/members/${revokeTarget.id}/revoke`);
      notify("دسترسی کارفرما لغو شد.", "success");
      setRevokeTarget(null);
      members.reload();
      onProjectChanged();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <MessageCircle size={16} className="text-[#b9a7ff]" aria-hidden />
          اتصال کارفرما در تلگرام
        </h2>
        <ol className="mt-3 grid gap-2 text-[11px] leading-6 text-muted sm:grid-cols-2">
          <li>۱. کد لایسنس پروژه را از تب لایسنس صادر و به کارفرما برسانید.</li>
          <li>۲. کارفرما ربات مرکزی نت نووا را باز می کند و Start را می زند.</li>
          <li>۳. کد لایسنس را برای ربات ارسال می کند.</li>
          <li>۴. درخواست او در همین صفحه نمایش داده می شود و پس از تایید شما دسترسی فعال می شود.</li>
        </ol>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {project.license ? (
            <span className="inline-flex items-center gap-2 rounded-lg bg-elevated px-2.5 py-1.5 text-[11px]">
              پیشوند لایسنس:
              <code dir="ltr">{project.license.code_prefix}•••</code>
              <CopyButton value={project.license.code_prefix} label="کپی پیشوند" variant="ghost" />
            </span>
          ) : (
            <Badge tone="danger">برای این پروژه لایسنس فعالی وجود ندارد</Badge>
          )}
          <span className="text-[10px] text-muted">
            MVP: هر پروژه یک کارفرمای اصلی دارد.
          </span>
        </div>
      </div>

      {members.error && !members.data ? (
        <div className="panel">
          <ErrorState message={members.error} onRetry={members.reload} />
        </div>
      ) : members.loading && !members.data ? (
        <div className="panel">
          <SkeletonRows rows={3} />
        </div>
      ) : (
        <>
          {pending.length > 0 ? (
            <section className="panel border-warning/30">
              <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
                <h2 className="text-sm font-semibold">در انتظار تایید</h2>
                <Badge tone="warning">{pending.length}</Badge>
              </div>
              <ul className="divide-y divide-line-soft">
                {pending.map((member) => (
                  <li
                    key={member.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="text-sm font-medium">{member.display_name}</p>
                      <p className="mt-0.5 text-[11px] text-muted" dir="ltr">
                        Telegram ID: {member.telegram_id} · {formatTelegramHandle(member.username)}
                      </p>
                      <p className="text-[10px] text-muted">
                        درخواست در {formatDateTime(member.created_at)}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => setApproveTarget(member)}>
                        <Check size={14} aria-hidden />
                        تایید اتصال
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setRevokeTarget(member)}
                      >
                        <UserX size={14} aria-hidden />
                        رد درخواست
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3.5">
              <h2 className="text-sm font-semibold">کاربران مجاز</h2>
              <Badge tone={active.length ? "success" : "neutral"}>{active.length} فعال</Badge>
            </div>
            {active.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck size={22} aria-hidden />}
                title="کارفرمای متصلی وجود ندارد"
                description="پس از ارسال کد لایسنس توسط کارفرما به ربات، درخواست او در همین صفحه برای تایید نمایش داده می شود."
              />
            ) : (
              <ul className="divide-y divide-line-soft">
                {active.map((member) => (
                  <li key={member.id} className="p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-3">
                        <span className="flex size-9 items-center justify-center rounded-lg border border-line bg-elevated text-sm">
                          {member.display_name.slice(0, 1)}
                        </span>
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-medium">{member.display_name}</p>
                            <MemberStatusBadge status={member.status} />
                          </div>
                          <p className="mt-0.5 text-[11px] text-muted" dir="ltr">
                            Telegram ID: {member.telegram_id} ·{" "}
                            {formatTelegramHandle(member.username)}
                          </p>
                          <p className="text-[10px] text-muted">
                            فعال سازی: {formatDateTime(member.activated_at)}
                          </p>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => setRevokeTarget(member)}
                      >
                        <UserX size={14} aria-hidden />
                        لغو دسترسی
                      </Button>
                    </div>
                    <MemberChannels
                      projectId={project.id}
                      member={member}
                      channels={project.channels}
                      onChanged={() => {
                        members.reload();
                        onProjectChanged();
                      }}
                    />
                  </li>
                ))}
              </ul>
            )}
          </section>

          {revoked.length > 0 ? (
            <section className="panel overflow-hidden">
              <div className="border-b border-line px-4 py-3.5">
                <h2 className="text-sm font-semibold">تاریخچه دسترسی</h2>
              </div>
              <ul className="divide-y divide-line-soft">
                {revoked.map((member) => (
                  <li key={member.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <div>
                      <p className="text-xs">{member.display_name}</p>
                      <p className="text-[10px] text-muted" dir="ltr">
                        Telegram ID: {member.telegram_id}
                      </p>
                    </div>
                    <MemberStatusBadge status={member.status} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}

      <div className="panel flex items-start gap-2 p-4 text-[10px] leading-6 text-muted">
        <Copy size={13} className="mt-1 shrink-0" aria-hidden />
        کد لایسنس را فقط از مسیر امن به کارفرما برسانید. مدیر نمی تواند کد کامل را دوباره
        ببیند؛ در صورت گم شدن، لایسنس جدید صادر و کد قبلی لغو می شود.
      </div>

      <ConfirmDialog
        open={Boolean(approveTarget)}
        onClose={() => setApproveTarget(null)}
        onConfirm={approve}
        loading={busy}
        title="تایید اتصال کارفرما"
        message={
          approveTarget
            ? `${approveTarget.display_name} به پروژه دسترسی پیدا می کند و پیام خوش آمدگویی برای او ارسال می شود.`
            : ""
        }
        confirmLabel="تایید اتصال"
      />
      <ConfirmDialog
        open={Boolean(revokeTarget)}
        onClose={() => setRevokeTarget(null)}
        onConfirm={revoke}
        loading={busy}
        tone="danger"
        title={revokeTarget?.status === "pending_approval" ? "رد درخواست" : "لغو دسترسی"}
        message="دسترسی این کاربر به پروژه متوقف می شود. لایسنس پروژه لغو نمی شود و سایر اطلاعات پروژه حفظ می ماند."
        confirmLabel={revokeTarget?.status === "pending_approval" ? "رد درخواست" : "لغو دسترسی"}
      />
    </div>
  );
}
