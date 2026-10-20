import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { LoginForm } from "@/features/auth/LoginForm";

const login = vi.fn();
const replace = vi.fn();

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ login }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/login",
}));

beforeEach(() => {
  login.mockReset();
  replace.mockReset();
});

describe("LoginForm", () => {
  it("renders all fields and the no-signup notice", () => {
    render(<LoginForm nextPath="/" />);
    expect(screen.getByLabelText("ایمیل مدیر")).toBeInTheDocument();
    expect(screen.getByLabelText("رمز عبور")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ورود به پنل/ })).toBeInTheDocument();
    expect(screen.getByText(/ایجاد حساب کاربری عمومی وجود ندارد/)).toBeInTheDocument();
  });

  it("shows Persian validation messages before calling the API", async () => {
    render(<LoginForm nextPath="/" />);
    await userEvent.click(screen.getByRole("button", { name: /ورود به پنل/ }));
    expect(await screen.findByText("ایمیل را وارد کنید.")).toBeInTheDocument();
    expect(screen.getByText("رمز عبور را وارد کنید.")).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it("rejects malformed email formats", async () => {
    render(<LoginForm nextPath="/" />);
    await userEvent.type(screen.getByLabelText("ایمیل مدیر"), "admin@");
    await userEvent.type(screen.getByLabelText("رمز عبور"), "secret");
    await userEvent.click(screen.getByRole("button", { name: /ورود به پنل/ }));
    expect(await screen.findByText("ایمیل وارد شده معتبر نیست.")).toBeInTheDocument();
  });

  it("shows the server error message for bad credentials", async () => {
    login.mockRejectedValue(
      new ApiError(401, "invalid_credentials", "ایمیل یا رمز عبور صحیح نیست."),
    );
    render(<LoginForm nextPath="/" />);
    await userEvent.type(screen.getByLabelText("ایمیل مدیر"), "admin@netnova.ir");
    await userEvent.type(screen.getByLabelText("رمز عبور"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /ورود به پنل/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("ایمیل یا رمز عبور صحیح نیست.");
    expect(replace).not.toHaveBeenCalled();
  });

  it("navigates to the requested page after a successful login", async () => {
    login.mockResolvedValue(undefined);
    render(<LoginForm nextPath="/projects" />);
    await userEvent.type(screen.getByLabelText("ایمیل مدیر"), "admin@netnova.ir");
    await userEvent.type(screen.getByLabelText("رمز عبور"), "correct-password");
    await userEvent.click(screen.getByRole("button", { name: /ورود به پنل/ }));
    expect(login).toHaveBeenCalledWith("admin@netnova.ir", "correct-password");
    expect(replace).toHaveBeenCalledWith("/projects");
  });
});
