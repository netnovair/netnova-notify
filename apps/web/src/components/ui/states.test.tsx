import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Badge } from "@/components/ui/Badge";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  SkeletonRows,
} from "@/components/ui/States";
import { NotificationStatusBadge, PaymentStatusBadge } from "@/components/ui/StatusBadge";

describe("state components", () => {
  it("announces loading state", () => {
    render(<LoadingState label="در حال دریافت پروژه ها..." />);
    expect(screen.getByRole("status")).toHaveTextContent("در حال دریافت پروژه ها...");
  });

  it("renders a skeleton loading placeholder", () => {
    render(<SkeletonRows rows={3} />);
    expect(screen.getByRole("status", { name: "در حال بارگذاری" })).toBeInTheDocument();
  });

  it("shows empty state copy and action", () => {
    render(
      <EmptyState
        title="هنوز پروژه ای ثبت نشده است"
        description="اولین پروژه را ایجاد کنید."
        action={<button type="button">ایجاد پروژه</button>}
      />,
    );
    expect(screen.getByText("هنوز پروژه ای ثبت نشده است")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ایجاد پروژه" })).toBeInTheDocument();
  });

  it("shows an error with a retry action", async () => {
    const retry = vi.fn();
    render(<ErrorState message="سرور در دسترس نیست." onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("سرور در دسترس نیست.");
    await userEvent.click(screen.getByRole("button", { name: /تلاش دوباره/ }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("maps operational statuses to Persian labels", () => {
    render(
      <>
        <NotificationStatusBadge status="queued" />
        <NotificationStatusBadge status="failed" />
        <PaymentStatusBadge status="unpaid" isOverdue={false} />
        <PaymentStatusBadge status="unpaid" isOverdue={true} />
        <Badge tone="info">نمایشی</Badge>
      </>,
    );
    expect(screen.getByText("در صف ارسال")).toBeInTheDocument();
    expect(screen.getByText("ناموفق")).toBeInTheDocument();
    expect(screen.getByText("پرداخت نشده")).toBeInTheDocument();
    expect(screen.getByText("سررسید گذشته")).toBeInTheDocument();
    expect(screen.getByText("نمایشی")).toBeInTheDocument();
  });
});
