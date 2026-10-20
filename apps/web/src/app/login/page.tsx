"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Eye, EyeOff, Loader2, LockKeyhole, Mail } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/components/auth/AuthProvider";
import { Logo, LogoMark } from "@/components/brand/Logo";
import { errorMessage } from "@/lib/api";
import { loginSchema, type LoginValues } from "@/lib/validation";

function safeNext(value: string | null): string {
  if (!value) return "/";
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

function LoginScreen() {
  const { status, login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    if (status === "authenticated") {
      router.replace(next);
    }
  }, [status, next, router]);

  async function onSubmit(values: LoginValues) {
    setServerError(null);
    try {
      await login(values.email, values.password);
      router.replace(next);
    } catch (error) {
      setServerError(errorMessage(error));
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center px-4 py-10">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -top-32 start-1/4 size-96 rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute -bottom-40 end-1/4 size-96 rounded-full bg-info/5 blur-3xl" />
      </div>

      <div className="relative w-full max-w-4xl overflow-hidden rounded-3xl border border-line bg-surface/80 shadow-2xl shadow-black/30 backdrop-blur md:grid md:grid-cols-[1fr_1fr]">
        <section className="hidden flex-col justify-between border-e border-line bg-elevated/30 p-8 md:flex">
          <Logo />
          <div>
            <h1 className="text-2xl font-semibold leading-relaxed">
              اطلاع رسانی پروژه ها،
              <br />
              یکجا و به موقع.
            </h1>
            <p className="mt-3 text-xs leading-7 text-muted">
              مدیریت لایسنس پروژه ها، ارسال اطلاعیه تلگرامی برای کارفرما و پیگیری
              پرداخت ها، از یک پنل امن.
            </p>
            <ul className="mt-6 space-y-3 text-[11px] text-muted">
              {[
                "ارسال از طریق ربات مرکزی تلگرام",
                "لایسنس مستقل برای هر پروژه",
                "صف پایدار ارسال و ثبت نتیجه",
                "ثبت کامل عملیات حساس در Audit",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-accent" aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[10px] leading-6 text-muted/80">
            دسترسی فقط برای مدیران مجاز نت نووا. کارفرماها از طریق ربات تلگرام وارد می
            شوند.
          </p>
        </section>

        <section className="p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-3 md:hidden">
            <LogoMark size={36} />
            <div>
              <p className="text-sm font-semibold">NetNova Notify</p>
              <p className="text-[10px] text-muted">مرکز اطلاع رسانی نت نووا</p>
            </div>
          </div>

          <h2 className="text-xl font-semibold">ورود مدیر</h2>
          <p className="mt-1 text-xs leading-6 text-muted">
            برای ادامه، اطلاعات حساب مدیریتی خود را وارد کنید.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
            {serverError ? (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/10 px-3 py-2.5 text-xs leading-6 text-[#ffb4b4]"
              >
                <AlertCircle size={15} className="mt-1 shrink-0" aria-hidden />
                <span>{serverError}</span>
              </div>
            ) : null}

            <div>
              <label htmlFor="email" className="field-label">
                ایمیل
              </label>
              <div className="relative">
                <Mail
                  size={15}
                  aria-hidden
                  className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted"
                />
                <input
                  id="email"
                  type="email"
                  inputMode="email"
                  autoComplete="username"
                  dir="ltr"
                  placeholder="admin@example.com"
                  className="field-input ps-9 text-start"
                  aria-invalid={errors.email ? "true" : undefined}
                  aria-describedby={errors.email ? "email-error" : undefined}
                  {...register("email")}
                />
              </div>
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
                <LockKeyhole
                  size={15}
                  aria-hidden
                  className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted"
                />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  dir="ltr"
                  placeholder="••••••••"
                  className="field-input px-9 text-start"
                  aria-invalid={errors.password ? "true" : undefined}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute end-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-muted transition hover:bg-white/5 hover:text-ink"
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
              className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 text-sm font-semibold text-white shadow-lg shadow-accent/25 transition hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? <Loader2 size={16} className="animate-spin" aria-hidden /> : null}
              {isSubmitting ? "در حال ورود..." : "ورود به پنل"}
            </button>
          </form>

          <div className="mt-5 rounded-xl border border-line-soft bg-elevated/40 px-3 py-2.5 text-[10px] leading-6 text-muted">
            حساب کاربری از طریق این صفحه ساخته نمی شود. در صورت فراموشی رمز عبور، با
            مدیر سیستم تماس بگیرید.
          </div>

          <p className="mt-6 text-center text-[10px] text-muted/70">
            نسخه MVP · NetNova Digital Marketing Agency
          </p>
        </section>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center">
          <Loader2 size={22} className="animate-spin text-accent" aria-hidden />
        </div>
      }
    >
      <LoginScreen />
    </Suspense>
  );
}
