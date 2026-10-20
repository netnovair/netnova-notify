import { z } from "zod";

const required = (message: string) => message;

export const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, required("ایمیل را وارد کنید."))
    .regex(/^[^\s@]+@[^\s@]+\.[^\s@]+$/, "ایمیل وارد شده معتبر نیست."),
  password: z.string().min(1, required("رمز عبور را وارد کنید.")),
});

export type LoginValues = z.infer<typeof loginSchema>;

const featureShape = z.object({
  announcements: z.boolean().optional(),
  financial: z.boolean().optional(),
  performance: z.boolean().optional(),
  progress: z.boolean().optional(),
  support: z.boolean().optional(),
});

export type FeatureValues = z.infer<typeof featureShape>;

export const projectSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "نام پروژه باید حداقل ۲ نویسه باشد.")
    .max(160, "نام پروژه حداکثر ۱۶۰ نویسه است."),
  client_name: z
    .string()
    .trim()
    .min(2, "نام کارفرما باید حداقل ۲ نویسه باشد.")
    .max(160, "نام کارفرما حداکثر ۱۶۰ نویسه است."),
  slug: z
    .string()
    .trim()
    .optional()
    .refine((value) => !value || /^[a-z0-9][a-z0-9-]{1,79}$/.test(value), {
      message: "شناسه باید با حروف کوچک انگلیسی، عدد و خط تیره باشد.",
    }),
  description: z.string().trim().max(4000, "توضیحات حداکثر ۴۰۰۰ نویسه است.").optional(),
  features: featureShape,
});

export type ProjectValues = z.infer<typeof projectSchema>;

export const notificationSchema = z.object({
  title: z
    .string()
    .trim()
    .min(2, "عنوان اطلاعیه باید حداقل ۲ نویسه باشد.")
    .max(200, "عنوان حداکثر ۲۰۰ نویسه است."),
  body: z
    .string()
    .trim()
    .min(2, "متن اطلاعیه باید حداقل ۲ نویسه باشد.")
    .max(3500, "متن اطلاعیه حداکثر ۳۵۰۰ نویسه است."),
  type: z.enum(["announcement", "financial", "system"]),
  scheduling: z.enum(["now", "later"]),
  scheduled_at: z.string().optional(),
}).superRefine((values, ctx) => {
  if (values.scheduling === "later") {
    if (!values.scheduled_at) {
      ctx.addIssue({
        code: "custom",
        path: ["scheduled_at"],
        message: "زمان ارسال را انتخاب کنید.",
      });
      return;
    }
    const date = new Date(values.scheduled_at);
    if (Number.isNaN(date.getTime())) {
      ctx.addIssue({ code: "custom", path: ["scheduled_at"], message: "زمان معتبر نیست." });
    } else if (date.getTime() < Date.now() + 60_000) {
      ctx.addIssue({
        code: "custom",
        path: ["scheduled_at"],
        message: "زمان زمان بندی باید در آینده باشد.",
      });
    }
  }
});

export type NotificationValues = z.infer<typeof notificationSchema>;

export const paymentSchema = z.object({
  title: z
    .string()
    .trim()
    .min(2, "عنوان پرداخت باید حداقل ۲ نویسه باشد.")
    .max(200, "عنوان حداکثر ۲۰۰ نویسه است."),
  amount: z
    .number({ message: "مبلغ را به صورت عدد وارد کنید." })
    .positive("مبلغ باید بزرگ تر از صفر باشد.")
    .max(1_000_000_000_000_000, "مبلغ وارد شده بسیار بزرگ است."),
  currency: z.enum(["IRR", "IRT", "USD", "EUR"]),
  due_at: z.string().min(1, "تاریخ سررسید را انتخاب کنید."),
  notes: z.string().trim().max(2000, "توضیحات حداکثر ۲۰۰۰ نویسه است.").optional(),
});

export type PaymentValues = z.infer<typeof paymentSchema>;

export const licenseSchema = z.object({
  expires_at: z.string().optional(),
});

export type LicenseValues = z.infer<typeof licenseSchema>;

/** Converts the admin-visible major amount to the integer stored by the API. */
export function amountToMinor(amount: number, currency: string): number {
  const factor = currency === "USD" || currency === "EUR" ? 100 : 1;
  return Math.round(amount * factor);
}
