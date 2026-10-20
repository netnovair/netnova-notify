import { describe, expect, it } from "vitest";

import {
  formatAmount,
  formatDate,
  formatDateTime,
  formatNumber,
  formatAge,
  formatRelative,
  fromDateTimeInput,
  toDateInput,
} from "@/lib/format";

describe("Persian formatting", () => {
  it("renders Jalali dates in Persian digits", () => {
    const value = formatDate("2026-10-19T12:00:00Z");
    expect(value).toContain("۱۴۰۵");
    expect(value).toContain("مهر");
    expect(value).toContain("۲۷");
  });

  it("renders date and time together", () => {
    const value = formatDateTime("2026-10-19T12:00:00Z");
    expect(value).toContain("۱۴۰۵");
    expect(value).toMatch(/[۰-۹]{2}:[۰-۹]{2}/);
  });

  it("uses a placeholder for missing dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("not-a-date")).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
  });

  it("formats numbers with Persian separators", () => {
    expect(formatNumber(1234567)).toBe("۱٬۲۳۴٬۵۶۷");
  });

  it("formats amounts with explicit currency and minor units", () => {
    expect(formatAmount(1_200_000, "IRT")).toBe("۱٬۲۰۰٬۰۰۰ تومان");
    expect(formatAmount(12_345, "USD")).toBe("۱۲۳٫۴۵ دلار");
    expect(formatAmount(5_000, "IRR")).toContain("ریال");
  });

  it("formats relative times", () => {
    const now = new Date("2026-10-19T12:00:00Z").getTime();
    expect(formatRelative("2026-10-19T11:59:40Z", now)).toBe("لحظه ای پیش");
    expect(formatRelative("2026-10-19T11:30:00Z", now)).toContain("دقیقه پیش");
    expect(formatRelative("2026-10-19T09:00:00Z", now)).toContain("ساعت پیش");
    expect(formatRelative(null, now)).toBe("—");
  });

  it("formats a known age without reading the clock", () => {
    expect(formatAge(10)).toBe("لحظه ای پیش");
    expect(formatAge(120)).toContain("دقیقه پیش");
    expect(formatAge(7200)).toContain("ساعت پیش");
    expect(formatAge(86400 * 10)).toContain("روز پیش");
    expect(formatAge(-30)).toBe("لحظه ای پیش");
  });

  it("round-trips datetime-local values", () => {
    const iso = fromDateTimeInput("2030-02-01T10:30");
    expect(iso).not.toBeNull();
    expect(toDateInput(iso)).toBe("2030-02-01");
    expect(fromDateTimeInput("")).toBeNull();
  });
});
