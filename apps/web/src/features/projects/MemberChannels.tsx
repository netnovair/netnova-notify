"use client";

import { Save, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { CHANNEL_LABELS } from "@/lib/labels";
import type { Member, ProjectChannel } from "@/types/api";

const SUPPORTED = ["bale", "eitaa", "smsir"] as const;

export function MemberChannels({
  projectId,
  member,
  channels,
  onChanged,
}: {
  projectId: string;
  member: Member;
  channels: ProjectChannel[];
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (member.channel_identities ?? []).map((identity) => [
        identity.channel,
        identity.external_id,
      ]),
    ),
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const enabled = new Set(channels.filter((channel) => channel.enabled).map((c) => c.channel));

  async function save(channel: string) {
    const value = (draft[channel] ?? "").trim();
    if (!value) return;
    setBusy(channel);
    setError(null);
    try {
      await api.put(
        `/projects/${projectId}/members/${member.id}/channels/${channel}`,
        { external_id: value },
      );
      notify(`مقصد ${CHANNEL_LABELS[channel] ?? channel} ذخیره شد.`, "success");
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  async function remove(channel: string) {
    setBusy(channel);
    setError(null);
    try {
      await api.del(`/projects/${projectId}/members/${member.id}/channels/${channel}`);
      setDraft((previous) => ({ ...previous, [channel]: "" }));
      notify(`مقصد ${CHANNEL_LABELS[channel] ?? channel} حذف شد.`, "success");
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-line-soft bg-bg/40 p-2.5">
      <p className="mb-2 text-[10px] leading-6 text-muted">
        مقصد این کارفرما در کانال های دیگر. تلگرام از هویت خود ربات استفاده می کند و نیازی
        به ثبت جداگانه ندارد. فقط کانال هایی که برای پروژه فعال شده اند معنا دارند.
      </p>
      {error ? (
        <p role="alert" className="mb-2 text-[10px] text-[#ffb4b4]">
          {error}
        </p>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-3">
        {SUPPORTED.map((channel) => {
          const saved = (member.channel_identities ?? []).find(
            (identity) => identity.channel === channel,
          );
          return (
            <div key={channel} className="space-y-1">
              <div className="flex items-center gap-1">
                <label
                  htmlFor={`channel-${member.id}-${channel}`}
                  className="text-[10px] text-muted"
                >
                  {CHANNEL_LABELS[channel]}
                </label>
                {enabled.has(channel) ? (
                  <Badge tone="success">فعال</Badge>
                ) : (
                  <Badge tone="neutral">غیرفعال برای پروژه</Badge>
                )}
              </div>
              <div className="flex items-center gap-1">
                <input
                  id={`channel-${member.id}-${channel}`}
                  dir="ltr"
                  value={draft[channel] ?? ""}
                  onChange={(event) =>
                    setDraft((previous) => ({ ...previous, [channel]: event.target.value }))
                  }
                  placeholder={channel === "smsir" ? "09xxxxxxxxx" : "chat id"}
                  className="h-8 w-full min-w-0 rounded-md border border-line bg-bg/70 px-2 text-[11px]"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  aria-label={`ذخیره ${CHANNEL_LABELS[channel]}`}
                  loading={busy === channel}
                  disabled={!(draft[channel] ?? "").trim()}
                  onClick={() => void save(channel)}
                >
                  <Save size={12} aria-hidden />
                </Button>
                {saved ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`حذف ${CHANNEL_LABELS[channel]}`}
                    loading={busy === channel}
                    onClick={() => void remove(channel)}
                  >
                    <Trash2 size={12} aria-hidden />
                  </Button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
