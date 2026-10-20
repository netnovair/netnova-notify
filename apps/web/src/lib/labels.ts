import type {
  Currency,
  OrderStatus,
  LicenseStatus,
  MemberStatus,
  NotificationStatus,
  NotificationType,
  PaymentStatus,
  ProjectStatus,
} from "@/types/api";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

type LabelSpec = { label: string; tone: Tone };

export const PROJECT_STATUS: Record<ProjectStatus, LabelSpec> = {
  active: { label: "فعال", tone: "success" },
  inactive: { label: "غیرفعال", tone: "neutral" },
};

export const LICENSE_STATUS: Record<LicenseStatus, LabelSpec> = {
  pending: { label: "در انتظار فعال سازی", tone: "warning" },
  active: { label: "فعال", tone: "success" },
  revoked: { label: "لغو شده", tone: "danger" },
  expired: { label: "منقضی شده", tone: "neutral" },
};

export const MEMBER_STATUS: Record<MemberStatus, LabelSpec> = {
  pending_approval: { label: "در انتظار تایید", tone: "warning" },
  active: { label: "متصل و فعال", tone: "success" },
  revoked: { label: "دسترسی لغو شده", tone: "danger" },
};

export const NOTIFICATION_STATUS: Record<NotificationStatus, LabelSpec> = {
  draft: { label: "پیش نویس", tone: "neutral" },
  queued: { label: "در صف ارسال", tone: "info" },
  sending: { label: "در حال ارسال", tone: "accent" },
  sent: { label: "ارسال شده", tone: "success" },
  failed: { label: "ناموفق", tone: "danger" },
  retry_wait: { label: "در انتظار تلاش مجدد", tone: "warning" },
  cancelled: { label: "لغو شده", tone: "neutral" },
};

export const DELIVERY_STATUS: Record<string, LabelSpec> = {
  pending: { label: "در انتظار", tone: "neutral" },
  sending: { label: "در حال ارسال", tone: "accent" },
  sent: { label: "ارسال شده", tone: "success" },
  failed: { label: "ناموفق", tone: "danger" },
  unknown: { label: "نتیجه نامشخص", tone: "warning" },
};

export const PAYMENT_STATUS: Record<PaymentStatus, LabelSpec> = {
  unpaid: { label: "پرداخت نشده", tone: "warning" },
  partially_paid: { label: "پرداخت جزئی", tone: "info" },
  paid: { label: "تسویه شده", tone: "success" },
  cancelled: { label: "لغو شده", tone: "neutral" },
};

export const RECEIPT_STATUS: Record<
  "pending" | "approved" | "rejected",
  LabelSpec
> = {
  pending: { label: "در انتظار بررسی", tone: "warning" },
  approved: { label: "تایید شده", tone: "success" },
  rejected: { label: "رد شده", tone: "danger" },
};

export const NOTIFICATION_TYPE: Record<NotificationType, string> = {
  announcement: "اطلاعیه",
  financial: "اطلاعیه مالی",
  system: "اطلاعیه سیستمی",
};

export const CURRENCY_OPTIONS: Array<{ value: Currency; label: string }> = [
  { value: "IRT", label: "تومان" },
  { value: "IRR", label: "ریال" },
  { value: "USD", label: "دلار" },
  { value: "EUR", label: "یورو" },
];

export const FEATURE_LABELS: Record<string, string> = {
  announcements: "اطلاعیه ها",
  financial: "اطلاعیه های مالی",
  performance: "گزارش عملکرد",
  progress: "پیشرفت پروژه",
  support: "پشتیبانی",
};

export const TICKET_STATUS: Record<string, LabelSpec> = {
  open: { label: "باز", tone: "info" },
  pending_admin: { label: "در انتظار پشتیبانی", tone: "warning" },
  pending_employer: { label: "در انتظار کارفرما", tone: "accent" },
  closed: { label: "بسته شده", tone: "neutral" },
};

export const TICKET_PRIORITY: Record<string, LabelSpec> = {
  low: { label: "کم", tone: "neutral" },
  normal: { label: "معمولی", tone: "info" },
  high: { label: "فوری", tone: "danger" },
};

export const CHANNEL_LABELS: Record<string, string> = {
  telegram: "تلگرام",
  bale: "بله",
  eitaa: "ایتا",
  smsir: "پیامک (sms.ir)",
};

export const JOB_STATUS_LABELS: Record<string, string> = {
  online: "در حال اجرا",
  offline: "متوقف",
  unknown: "بدون گزارش",
};

export const TELEGRAM_MODE_LABELS: Record<string, string> = {
  http: "ربات واقعی",
  mock: "حالت شبیه سازی",
};

export function labelFor(
  map: Record<string, LabelSpec>,
  key: string | null | undefined,
): LabelSpec {
  if (key && map[key]) return map[key];
  return { label: key ?? "—", tone: "neutral" };
}

export function paymentLabel(status: PaymentStatus, isOverdue: boolean): LabelSpec {
  if (status === "unpaid" && isOverdue) {
    return { label: "سررسید گذشته", tone: "danger" };
  }
  return PAYMENT_STATUS[status] ?? { label: status, tone: "neutral" };
}


export const ORDER_STATUS: Record<OrderStatus, LabelSpec> = {
  new: { label: "جدید", tone: "accent" },
  contacted: { label: "تماس گرفته شد", tone: "info" },
  quoted: { label: "پیشنهاد ارسال شد", tone: "warning" },
  won: { label: "تبدیل به مشتری", tone: "success" },
  lost: { label: "منصرف شد", tone: "danger" },
  cancelled: { label: "لغو شده", tone: "neutral" },
};

export const QUESTION_TYPES: Record<string, string> = {
  text: "متن کوتاه",
  long_text: "متن بلند",
  number: "عدد",
  choice: "انتخابی",
  phone: "شماره تماس",
};
