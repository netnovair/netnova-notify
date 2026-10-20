"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Eye, EyeOff, Loader2, LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/components/auth/AuthProvider";
import { errorMessage } from "@/lib/api";
import { loginSchema, type LoginValues } from "@/lib/validation";

export function LoginForm({ nextPath }: { nextPath: string }) {
  const { login } = useAuth();
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    setServerError(null);
    try {
      await login(values.email, values.password);
      router.replace(nextPath);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      {serverError ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/[0.07] px-4 py-3 text-xs leading-6 text-[#ffb4b4]"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
          <span>{serverError}</span>
        </div>
      ) : null}

      <div>
        <label htmlFor="email" className="field-label">
          ایمیل مدیر
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          inputMode="email"
          dir="ltr"
          className="field-input text-start"
          placeholder="admin@example.com"
          aria-invalid={errors.email ? "true" : undefined}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
        {errors.email ? (
          <p id="email-error" className="field-error">
            {errors.email.message}
          </p>
        ) : null}
      </div>

      <div>
        <label htmlFor="password" className="field-label">
          رمز عبور
        </label>
        <div className="relative">
          <input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            className="field-input pe-11"
            placeholder="••••••••"
            aria-invalid={errors.password ? "true" : undefined}
            aria-describedby={errors.password ? "password-error" : undefined}
            {...register("password")}
          />
          <button
            type="button"
            onClick={() => setShowPassword((value) => !value)}
            className="absolute end-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-muted hover:text-ink"
            aria-label={showPassword ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"}
          >
            {showPassword ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
          </button>
        </div>
        {errors.password ? (
          <p id="password-error" className="field-error">
            {errors.password.message}
          </p>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-2 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent text-sm font-medium text-white shadow-lg shadow-accent/20 transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? (
          <Loader2 size={16} className="animate-spin" aria-hidden />
        ) : (
          <LogIn size={16} aria-hidden />
        )}
        {isSubmitting ? "در حال ورود..." : "ورود به پنل"}
      </button>

      <p className="pt-2 text-center text-[11px] leading-6 text-muted">
        ایجاد حساب کاربری عمومی وجود ندارد. حساب مدیر فقط توسط owner سیستم ساخته می شود.
      </p>
    </form>
  );
}
