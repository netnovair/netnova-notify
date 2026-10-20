"use client";

import { Download, MonitorSmartphone, ShieldCheck, WifiOff } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { useOnlineStatus } from "@/lib/hooks";

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

const subscribeInstall = (callback: () => void) => {
  window.addEventListener("appinstalled", callback);
  return () => window.removeEventListener("appinstalled", callback);
};

const subscribeNothing = () => () => {};

function isInstalled(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function InstallCard() {
  const { notify } = useToast();
  const [promptEvent, setPromptEvent] = useState<InstallPromptEvent | null>(null);
  const [swReady, setSwReady] = useState(false);
  const installed = useSyncExternalStore(subscribeInstall, isInstalled, () => false);
  const secure = useSyncExternalStore(
    subscribeNothing,
    () => window.isSecureContext,
    () => false,
  );
  const online = useOnlineStatus();

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setPromptEvent(event as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .getRegistration()
        .then((registration) => setSwReady(Boolean(registration?.active)));
    }
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  async function install() {
    if (!promptEvent) return;
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    if (choice.outcome === "accepted") {
      notify("نصب برنامه آغاز شد.", "success");
    } else {
      notify("نصب لغو شد.", "info");
    }
    setPromptEvent(null);
  }

  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <MonitorSmartphone size={17} className="text-[#b9a7ff]" aria-hidden />
          <h2 className="text-sm font-semibold">برنامه نصب شونده (PWA)</h2>
        </div>
        <Badge tone={installed ? "success" : "neutral"} dot>
          {installed ? "نصب شده" : "قابل نصب"}
        </Badge>
      </div>

      <ul className="space-y-2 text-[11px] leading-6 text-muted">
        <li className="flex items-center justify-between gap-2 border-b border-line-soft pb-2">
          <span className="flex items-center gap-1.5">
            <ShieldCheck size={13} aria-hidden />
            اتصال امن HTTPS
          </span>
          <Badge tone={secure ? "success" : "warning"}>{secure ? "برقرار" : "برقرار نیست"}</Badge>
        </li>
        <li className="flex items-center justify-between gap-2 border-b border-line-soft pb-2">
          <span className="flex items-center gap-1.5">
            <WifiOff size={13} aria-hidden />
            Service Worker و صفحه آفلاین
          </span>
          <Badge tone={swReady ? "success" : "neutral"}>
            {swReady ? "فعال" : "ثبت نشده"}
          </Badge>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span>وضعیت شبکه</span>
          <Badge tone={online ? "success" : "warning"} dot>
            {online ? "متصل" : "آفلاین"}
          </Badge>
        </li>
      </ul>

      <p className="mt-3 text-[10px] leading-6 text-muted">
        در حالت آفلاین فقط پوسته برنامه و راهنمای قطعی اتصال نمایش داده می شود. داده های
        خصوصی و APIها توسط Service Worker ذخیره نمی شوند و عملیات نیازمند سرور آفلاین
        انجام نمی شود.
      </p>

      {!installed ? (
        <div className="mt-4">
          {promptEvent ? (
            <Button size="sm" onClick={() => void install()} block>
              <Download size={14} aria-hidden />
              نصب روی این دستگاه
            </Button>
          ) : (
            <p className="rounded-xl border border-line-soft bg-elevated/40 px-3 py-2.5 text-[10px] leading-6 text-muted">
              برای نصب در Android از منوی مرورگر «Add to Home screen» و در Desktop از
              آیکون نصب در نوار نشانی استفاده کنید. اگر گزینه نصب دیده نمی شود، باید سایت
              از طریق HTTPS باز شده باشد.
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-success/25 bg-success/[0.06] px-3 py-2.5 text-[10px] leading-6 text-[#a5efd4]">
          برنامه در حالت standalone اجرا می شود.
        </p>
      )}
    </section>
  );
}
