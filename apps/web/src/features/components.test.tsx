import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";
import { LicenseRevealModal } from "@/features/licenses/LicenseRevealModal";
import { NotificationActions } from "@/features/notifications/NotificationActions";
import { PaymentActions } from "@/features/payments/PaymentActions";
import { OverviewTab } from "@/features/projects/OverviewTab";
import type { NotificationListItem, Payment, Project } from "@/types/api";

function wrap(ui: React.ReactNode) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

const notificationBase: NotificationListItem = {
  id: "11111111-1111-4111-8111-111111111111",
  project_id: "22222222-2222-4222-8222-222222222222",
  project_name: "پروژه تست",
  type: "announcement",
  title: "اطلاعیه",
  status: "queued",
  scheduled_at: null,
  sent_at: null,
  attempt_count: 0,
  last_error: null,
  is_mock: false,
  created_at: "2026-10-19T10:00:00Z",
};

const paymentBase: Payment = {
  id: "33333333-3333-4333-8333-333333333333",
  project_id: "22222222-2222-4222-8222-222222222222",
  project_name: "پروژه تست",
  title: "پرداخت",
  amount_minor: 5_000_000,
  currency: "IRT",
  due_at: "2026-11-01T20:30:00Z",
  status: "unpaid",
  notes: null,
  paid_at: null,
  cancelled_at: null,
  created_at: "2026-10-19T10:00:00Z",
  updated_at: "2026-10-19T10:00:00Z",
  is_overdue: false,
  next_reminder_at: "2026-10-29T20:30:00Z",
};

const projectBase: Project = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "فروشگاه آرمان",
  slug: "arman-shop",
  client_name: "آرمان تجارت",
  description: "پروژه نمونه",
  status: "active",
  is_demo: false,
  telegram_connected_at: "2026-10-18T10:00:00Z",
  archived_at: null,
  channels: [
    {
      channel: "telegram",
      label: "تلگرام",
      enabled: true,
      configured: true,
      mode: "mock",
      beta: false,
      recipient_hint: "شناسه عددی چت",
      settings: {},
    },
  ],
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-18T10:00:00Z",
  features: [
    { key: "announcements", label: "اطلاعیه ها", enabled: true, implemented: true },
    { key: "financial", label: "اطلاعیه های مالی", enabled: true, implemented: true },
    { key: "support", label: "پشتیبانی و تیکت", enabled: true, implemented: true },
    { key: "performance", label: "گزارش عملکرد", enabled: true, implemented: false },
    { key: "progress", label: "پیشرفت پروژه", enabled: false, implemented: false },
  ],
  license: {
    id: "44444444-4444-4444-8444-444444444444",
    project_id: "22222222-2222-4222-8222-222222222222",
    code_prefix: "NN-AB",
    status: "active",
    effective_status: "active",
    expires_at: "2027-10-01T10:00:00Z",
    activated_at: "2026-10-02T10:00:00Z",
    revoked_at: null,
    created_at: "2026-10-01T10:00:00Z",
  },
  members: [
    {
      id: "55555555-5555-4555-8555-555555555555",
      telegram_id: 123456789,
      display_name: "کارفرمای آرمان",
      username: "arman",
      role: "owner",
      status: "active",
      activated_at: "2026-10-02T10:00:00Z",
      created_at: "2026-10-02T09:00:00Z",
    },
  ],
  open_payments_count: 2,
  notifications_count: 4,
};

describe("notification actions", () => {
  it("offers send-now and cancel for queued notifications", () => {
    wrap(
      <NotificationActions notification={notificationBase} onChanged={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /ارسال فوری/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /لغو ارسال/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /تلاش دوباره/ })).not.toBeInTheDocument();
  });

  it("offers retry for failed notifications only", () => {
    wrap(
      <NotificationActions
        notification={{ ...notificationBase, status: "failed" }}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /تلاش دوباره/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ارسال فوری/ })).not.toBeInTheDocument();
  });

  it("does not offer actions for delivered notifications", () => {
    wrap(
      <NotificationActions
        notification={{ ...notificationBase, status: "sent" }}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("payment actions", () => {
  it("allows settling and cancelling an unpaid payment", () => {
    wrap(
      <PaymentActions payment={paymentBase} onEdit={vi.fn()} onChanged={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /تسویه شد/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /لغو/ })).toBeInTheDocument();
  });

  it("freezes settled payments", () => {
    wrap(
      <PaymentActions
        payment={{ ...paymentBase, status: "paid" }}
        onEdit={vi.fn()}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText("اتمام یافته")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /تسویه شد/ })).not.toBeInTheDocument();
  });
});

describe("license reveal", () => {
  it("warns that the code is shown only once", () => {
    wrap(
      <LicenseRevealModal
        open
        onClose={vi.fn()}
        code="NN-ABCD-EFGH-JKMN-PQRS"
        projectName="فروشگاه آرمان"
      />,
    );
    expect(screen.getByText("NN-ABCD-EFGH-JKMN-PQRS")).toBeInTheDocument();
    expect(screen.getByText(/فقط همین یک بار/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /کپی کد/ })).toBeInTheDocument();
  });
});

describe("project overview", () => {
  it("labels unimplemented features as coming soon and hides raw codes", () => {
    render(
      <OverviewTab
        project={projectBase}
        onNavigate={vi.fn()}
        onNewNotification={vi.fn()}
        onNewPayment={vi.fn()}
      />,
    );
    expect(screen.getByText("آرمان تجارت")).toBeInTheDocument();
    expect(screen.getAllByText("به زودی").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/NN-ABCD-EFGH/)).not.toBeInTheDocument();
    expect(screen.getByText(/کارفرمای آرمان/)).toBeInTheDocument();
  });
});
