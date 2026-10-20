import type { Currency } from "@/types/api";

const DATE_LOCALE = "fa-IR-u-ca-persian";
const TIME_ZONE = "Asia/Tehran";

const dateFormatter = new Intl.DateTimeFormat(DATE_LOCALE, {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "long",
  day: "numeric",
});

const shortDateFormatter = new Intl.DateTimeFormat(DATE_LOCALE, {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const dateTimeFormatter = new Intl.DateTimeFormat(DATE_LOCALE, {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const timeFormatter = new Intl.DateTimeFormat(DATE_LOCALE, {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const CURRENCY_LABELS: Record<Currency, string> = {
  IRR: "ریال",
  IRT: "تومان",
  USD: "دلار",
  EUR: "یورو",
};

const MINOR_FACTOR: Record<Currency, number> = { IRR: 1, IRT: 1, USD: 100, EUR: 100 };

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return dateFormatter.format(date);
}

export function formatShortDate(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return shortDateFormatter.format(date);
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return dateTimeFormatter.format(date);
}

export function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return timeFormatter.format(date);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

export function formatAmount(amountMinor: number, currency: Currency): string {
  const factor = MINOR_FACTOR[currency] ?? 1;
  const value = amountMinor / factor;
  const formatter = new Intl.NumberFormat("fa-IR", {
    minimumFractionDigits: factor === 1 ? 0 : 2,
    maximumFractionDigits: factor === 1 ? 0 : 2,
  });
  return `${formatter.format(value)} ${CURRENCY_LABELS[currency] ?? currency}`;
}

/**
 * «۱۲ دقیقه پیش» for a duration that is already known.
 *
 * Kept free of `Date.now()` so components can format an age during render
 * without reading the clock (React purity rules); callers that have a
 * timestamp use :func:`formatRelative` instead.
 */
export function formatAge(seconds: number): string {
  const diff = Math.max(0, Math.round(seconds));
  if (diff < 45) return "لحظه ای پیش";
  if (diff < 3600) return `${formatNumber(Math.round(diff / 60))} دقیقه پیش`;
  if (diff < 86400) return `${formatNumber(Math.round(diff / 3600))} ساعت پیش`;
  if (diff < 86400 * 30) return `${formatNumber(Math.round(diff / 86400))} روز پیش`;
  return `${formatNumber(Math.round(diff / (86400 * 30)))} ماه پیش`;
}

export function formatRelative(iso?: string | null, now = Date.now()): string {
  if (!iso) return "—";
  const date = new Date(iso).getTime();
  if (Number.isNaN(date)) return "—";
  const diff = Math.round((now - date) / 1000);
  if (diff < 86400 * 7) return formatAge(diff);
  return formatDate(iso);
}

/** Converts an ISO string into a value usable by datetime-local inputs. */
export function toDateTimeInput(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

/** Minimal-safe date value for date inputs. */
export function toDateInput(iso?: string | null): string {
  return toDateTimeInput(iso).slice(0, 10);
}

/** Converts a datetime-local value to an ISO string (browser-local time). */
export function fromDateTimeInput(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export function formatTelegramHandle(username: string | null): string {
  return username ? `@${username}` : "بدون نام کاربری";
}

export function bytesToReadable(size: number): string {
  if (size < 1024) return `${formatNumber(size)} بایت`;
  if (size < 1024 * 1024) return `${formatNumber(Math.round(size / 1024))} کیلوبایت`;
  return `${formatNumber(Math.round((size / (1024 * 1024)) * 10) / 10)} مگابایت`;
}
