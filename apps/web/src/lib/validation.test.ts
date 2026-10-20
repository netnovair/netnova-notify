import { describe, expect, it } from "vitest";

import {
  amountToMinor,
  licenseSchema,
  loginSchema,
  notificationSchema,
  paymentSchema,
  projectSchema,
} from "@/lib/validation";

describe("login validation", () => {
  it("requires a valid email and password", () => {
    const empty = loginSchema.safeParse({ email: "", password: "" });
    expect(empty.success).toBe(false);
    const messages = empty.error?.issues.map((issue) => issue.message) ?? [];
    expect(messages).toContain("ایمیل را وارد کنید.");
    expect(messages).toContain("رمز عبور را وارد کنید.");

    expect(loginSchema.safeParse({ email: "not-an-email", password: "x" }).success).toBe(false);
    expect(loginSchema.safeParse({ email: "admin@netnova.ir", password: "secret" }).success).toBe(
      true,
    );
  });
});

describe("project validation", () => {
  it("rejects short names and invalid slugs", () => {
    const short = projectSchema.safeParse({
      name: "ا",
      client_name: "ب",
      features: {},
    });
    expect(short.success).toBe(false);

    const badSlug = projectSchema.safeParse({
      name: "پروژه معتبر",
      client_name: "کارفرمای معتبر",
      slug: "Bad Slug",
      features: {},
    });
    expect(badSlug.success).toBe(false);

    const good = projectSchema.safeParse({
      name: "پروژه معتبر",
      client_name: "کارفرمای معتبر",
      slug: "valid-slug",
      features: { announcements: true },
    });
    expect(good.success).toBe(true);
  });
});

describe("notification validation", () => {
  const base = {
    title: "نسخه جدید",
    body: "متن اطلاعیه",
    type: "announcement" as const,
    scheduling: "now" as const,
  };

  it("accepts immediate notifications", () => {
    expect(notificationSchema.safeParse(base).success).toBe(true);
  });

  it("requires a future date for scheduled notifications", () => {
    const missing = notificationSchema.safeParse({ ...base, scheduling: "later" });
    expect(missing.success).toBe(false);

    const past = notificationSchema.safeParse({
      ...base,
      scheduling: "later",
      scheduled_at: new Date(Date.now() - 3600_000).toISOString(),
    });
    expect(past.success).toBe(false);

    const future = notificationSchema.safeParse({
      ...base,
      scheduling: "later",
      scheduled_at: new Date(Date.now() + 86_400_000).toISOString(),
    });
    expect(future.success).toBe(true);
  });

  it("limits body length", () => {
    expect(
      notificationSchema.safeParse({ ...base, body: "x".repeat(3501) }).success,
    ).toBe(false);
  });
});

describe("payment validation", () => {
  const base = {
    title: "پرداخت مرحله اول",
    amount: 1_000_000,
    currency: "IRT" as const,
    due_at: "2030-01-01",
    notes: "",
  };

  it("requires a positive amount and due date", () => {
    expect(paymentSchema.safeParse({ ...base, amount: 0 }).success).toBe(false);
    expect(paymentSchema.safeParse({ ...base, amount: -5 }).success).toBe(false);
    expect(paymentSchema.safeParse({ ...base, due_at: "" }).success).toBe(false);
    expect(paymentSchema.safeParse(base).success).toBe(true);
  });

  it("converts major units to stored minor units", () => {
    expect(amountToMinor(1_200_000, "IRT")).toBe(1_200_000);
    expect(amountToMinor(12.34, "USD")).toBe(1234);
    expect(amountToMinor(99.999, "EUR")).toBe(10000);
  });

  it("allows an optional license expiry", () => {
    expect(licenseSchema.safeParse({}).success).toBe(true);
  });
});
