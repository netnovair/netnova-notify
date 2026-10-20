import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/layout/AppShell";

const authState = {
  status: "authenticated" as "authenticated" | "anonymous" | "loading" | "error",
  admin: { id: "1", email: "admin@netnova.ir", display_name: "مدیر نت", last_login_at: null },
  error: null as string | null,
  login: vi.fn(),
  logout: vi.fn(),
  refresh: vi.fn(),
};

const replace = vi.fn();

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => authState,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  replace.mockReset();
  authState.status = "authenticated";
});

describe("AppShell", () => {
  it("renders the Persian navigation for an authenticated admin", () => {
    render(
      <AppShell>
        <p>محتوای صفحه</p>
      </AppShell>,
    );
    expect(screen.getByText("محتوای صفحه")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /خانه/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /پروژه ها/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /تاریخچه ارسال/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /پرداخت ها/ }).length).toBeGreaterThan(0);
    expect(screen.getByRole("navigation", { name: "ناوبری موبایل" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "ناوبری اصلی" })).toBeInTheDocument();
    expect(screen.getAllByText("مدیر نت").length).toBeGreaterThan(0);
  });

  it("redirects anonymous visitors to login and preserves the target", async () => {
    authState.status = "anonymous";
    render(
      <AppShell>
        <p>محرمانه</p>
      </AppShell>,
    );
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/login?next=%2F");
    });
    expect(screen.queryByText("محرمانه")).not.toBeInTheDocument();
  });

  it("shows a session error with retry instead of content", () => {
    authState.status = "error";
    authState.error = "ارتباط با سرور برقرار نشد.";
    render(
      <AppShell>
        <p>محرمانه</p>
      </AppShell>,
    );
    expect(screen.getByText("ارتباط با سرور برقرار نشد")).toBeInTheDocument();
    expect(screen.getByText("ارتباط با سرور برقرار نشد.")).toBeInTheDocument();
    expect(screen.queryByText("محرمانه")).not.toBeInTheDocument();
  });

  it("never renders private content during session loading", () => {
    authState.status = "loading";
    render(
      <AppShell>
        <p>محرمانه</p>
      </AppShell>,
    );
    expect(screen.getByText("در حال بررسی نشست...")).toBeInTheDocument();
    expect(screen.queryByText("محرمانه")).not.toBeInTheDocument();
  });
});
