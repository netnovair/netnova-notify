"use client";

import { Radio, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import type { ChannelState } from "@/types/api";

export function ChannelsCard() {
  const channels = useApiData<ChannelState[]>(
    (signal) => api.get<ChannelState[]>("/channels", signal),
    [],
  );

  return (
    <section className="panel p-5 lg:col-span-2">
      <div className="mb-3 flex items-center gap-2">
        <Radio size={17} className="text-[#b9a7ff]" aria-hidden />
        <h2 className="text-sm font-semibold">کانال های ارسال</h2>
        <Button
          size="sm"
          variant="ghost"
          className="ms-auto"
          onClick={channels.reload}
          aria-label="به روزرسانی وضعیت کانال ها"
        >
          <RefreshCw size={13} aria-hidden />
        </Button>
      </div>
      <p className="mb-3 text-[11px] leading-6 text-muted">
        وضعیت واقعی اتصال سرویس دهنده ها روی سرور. کلیدها فقط در متغیرهای محیطی نگهداری می
        شوند و در این صفحه نمایش داده نمی شوند. فعال سازی هر کانال برای هر پروژه در تب
        «قابلیت ها و کانال ها» انجام می شود.
      </p>

      {channels.error && !channels.data ? (
        <ErrorState message={channels.error} onRetry={channels.reload} compact />
      ) : channels.loading && !channels.data ? (
        <SkeletonRows rows={4} />
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {(channels.data ?? []).map((channel) => (
            <li
              key={channel.key}
              className="rounded-xl border border-line-soft bg-elevated/30 px-3 py-2.5"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-medium">{channel.label}</span>
                {channel.beta ? <Badge tone="info">بتا</Badge> : null}
                {channel.configured ? (
                  <Badge tone="success">تنظیم شده</Badge>
                ) : (
                  <Badge tone="neutral">تنظیم نشده</Badge>
                )}
                <Badge tone={channel.mode === "mock" ? "mock" : "neutral"}>
                  {channel.mode === "mock" ? "شبیه سازی" : channel.mode}
                </Badge>
              </div>
              <p className="mt-1 text-[10px] leading-6 text-muted">{channel.description}</p>
              <p className="text-[10px] leading-6 text-muted">
                فرمت مقصد: <code dir="ltr">{channel.recipient_hint}</code>
              </p>
            </li>
          ))}
        </ul>
      )}

      {channels.data?.some((channel) => !channel.configured) ? (
        <div className="mt-3">
          <InlineAlert tone="info">
            کانال هایی که «تنظیم نشده» هستند تا وقتی کلیدهایشان در محیط سرور قرار نگیرد
            غیرفعال می مانند و هیچ پیامی از آن ها ارسال نمی شود.
          </InlineAlert>
        </div>
      ) : null}
    </section>
  );
}
