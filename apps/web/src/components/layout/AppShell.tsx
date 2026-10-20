"use client";

import clsx from "clsx";
import {
  BellRing,
  ClipboardList,
  FolderKanban,
  Home,
  KeyRound,
  Layers,
  LogOut,
  MessagesSquare,
  Settings,
  Wallet,
  WifiOff,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { LogoMark } from "@/components/brand/Logo";
import { useOnlineStatus } from "@/lib/hooks";

const NAV = [
  { href: "/", label: "خانه", icon: Home, short: "خانه" },
  { href: "/projects", label: "پروژه ها", icon: FolderKanban, short: "پروژه ها" },
  { href: "/orders", label: "سفارش ها", icon: ClipboardList, short: "سفارش" },
  { href: "/services", label: "خدمات", icon: Layers, short: "خدمات" },
  { href: "/licenses", label: "لایسنس ها", icon: KeyRound, short: "لایسنس" },
  { href: "/notifications", label: "تاریخچه ارسال", icon: BellRing, short: "اطلاعیه" },
  { href: "/payments", label: "پرداخت ها", icon: Wallet, short: "پرداخت" },
  { href: "/tickets", label: "پشتیبانی", icon: MessagesSquare, short: "پشتیبانی" },
  { href: "/settings", label: "تنظیمات", icon: Settings, short: "تنظیمات" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-xs leading-6 text-[#f7d478]"
    >
      <WifiOff size={15} aria-hidden className="shrink-0" />
      <span>
        اتصال اینترنت قطع است. نمایش داده ها ممکن است قدیمی باشد و عملیات جدید انجام نمی
        شود تا اتصال برقرار شود.
      </span>
    </div>
  );
}

function LoadingScreen({ label }: { label: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-6">
      <div role="status" className="flex flex-col items-center gap-3 text-muted">
        <LogoMark size={40} />
        <p className="text-sm">{label}</p>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status, admin, logout, refresh, error } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") {
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/login?next=${next}`);
    }
  }, [status, pathname, router]);

  if (status === "loading") {
    return <LoadingScreen label="در حال بررسی نشست..." />;
  }

  if (status === "error") {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="panel max-w-sm p-6 text-center">
          <h1 className="text-base font-semibold">ارتباط با سرور برقرار نشد</h1>
          <p className="mt-2 text-xs leading-7 text-muted">
            {error ?? "دریافت وضعیت نشست ممکن نشد. اتصال سرور و شبکه را بررسی کنید."}
          </p>
          <button
            type="button"
            onClick={() => void refresh()}
            className="mt-5 inline-flex h-10 items-center justify-center rounded-xl bg-accent px-4 text-sm font-medium text-white hover:bg-accent-strong"
          >
            تلاش دوباره
          </button>
        </div>
      </div>
    );
  }

  if (status === "anonymous") {
    return <LoadingScreen label="در حال انتقال به صفحه ورود..." />;
  }

  return (
    <div className="min-h-dvh">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-[80] focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:text-white"
      >
        رفتن به محتوای اصلی
      </a>

      <aside
        className="fixed inset-y-0 start-0 z-40 hidden w-64 flex-col border-e border-line bg-surface/80 backdrop-blur lg:flex"
      >
        <div className="flex h-16 items-center gap-2.5 border-b border-line px-5">
          <LogoMark size={32} />
          <div className="leading-tight">
            <p className="text-sm font-semibold">NetNova Notify</p>
            <p className="text-[10px] text-muted">مرکز اطلاع رسانی</p>
          </div>
        </div>
        <nav aria-label="ناوبری اصلی" className="flex-1 space-y-1 overflow-y-auto p-3">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                  active
                    ? "bg-accent/15 text-ink ring-1 ring-inset ring-accent/25"
                    : "text-muted hover:bg-white/5 hover:text-ink",
                )}
              >
                <Icon size={18} aria-hidden className={active ? "text-[#b9a7ff]" : ""} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-line p-3">
          <div className="mb-2 flex items-center gap-2 rounded-xl bg-elevated/60 px-3 py-2">
            <span className="flex size-8 items-center justify-center rounded-full bg-accent/20 text-xs font-semibold text-[#c6b8ff]">
              {(admin?.display_name ?? "م").slice(0, 1)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">{admin?.display_name}</p>
              <p className="truncate text-[10px] text-muted" dir="ltr">
                {admin?.email}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-xs text-muted transition hover:bg-danger/10 hover:text-danger"
          >
            <LogOut size={15} aria-hidden />
            خروج از حساب
          </button>
        </div>
      </aside>

      <div className="lg:ms-64">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-line bg-bg/90 px-4 backdrop-blur lg:hidden">
          <Link href="/" className="flex items-center gap-2">
            <LogoMark size={28} />
            <span className="text-sm font-semibold">NetNova Notify</span>
          </Link>
          <div className="flex items-center gap-1">
            <Link
              href="/settings"
              aria-label="تنظیمات"
              className="rounded-lg p-2 text-muted hover:bg-white/5 hover:text-ink"
            >
              <Settings size={18} aria-hidden />
            </Link>
            <button
              type="button"
              onClick={() => void logout()}
              aria-label="خروج از حساب"
              className="rounded-lg p-2 text-muted hover:bg-white/5 hover:text-ink"
            >
              <LogOut size={18} aria-hidden />
            </button>
          </div>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-7xl px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8"
        >
          <OfflineBanner />
          {children}
        </main>
      </div>

      <nav
        aria-label="ناوبری موبایل"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        <ul className="mx-auto flex max-w-lg items-stretch justify-between px-1">
          {NAV.filter((item) => !["/licenses", "/services"].includes(item.href)).map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href} className="flex-1">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "flex flex-col items-center gap-0.5 py-2 text-[10px] transition",
                    active ? "text-[#c6b8ff]" : "text-muted",
                  )}
                >
                  <span
                    className={clsx(
                      "flex h-7 w-10 items-center justify-center rounded-full",
                      active && "bg-accent/15",
                    )}
                  >
                    <Icon size={17} aria-hidden />
                  </span>
                  {item.short}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
