import { Badge } from "@/components/ui/Badge";
import {
  DELIVERY_STATUS,
  LICENSE_STATUS,
  MEMBER_STATUS,
  NOTIFICATION_STATUS,
  PAYMENT_STATUS,
  PROJECT_STATUS,
  labelFor,
  paymentLabel,
} from "@/lib/labels";
import type {
  Delivery,
  LicenseStatus,
  MemberStatus,
  NotificationStatus,
  PaymentStatus,
  ProjectStatus,
} from "@/types/api";

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const spec = PROJECT_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export function LicenseStatusBadge({ status }: { status: LicenseStatus }) {
  const spec = LICENSE_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export function MemberStatusBadge({
  status,
}: {
  status: MemberStatus;
}) {
  const spec = MEMBER_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export function NotificationStatusBadge({
  status,
}: {
  status: NotificationStatus;
}) {
  const spec = NOTIFICATION_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export function DeliveryStatusBadge({ status }: { status: Delivery["status"] }) {
  const spec = labelFor(DELIVERY_STATUS, status);
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export function PaymentStatusBadge({
  status,
  isOverdue,
}: {
  status: PaymentStatus;
  isOverdue: boolean;
}) {
  const spec = paymentLabel(status, isOverdue);
  if (status === "unpaid" && !isOverdue) {
    return <Badge tone={PAYMENT_STATUS.unpaid.tone}>{PAYMENT_STATUS.unpaid.label}</Badge>;
  }
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}
