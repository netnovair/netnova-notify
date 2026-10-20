"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ApiError,
  api,
  errorMessage,
  hasBearerToken,
  loadBearerToken,
  setBearerToken,
  setCsrfToken,
} from "@/lib/api";
import { reportPreviewSession } from "@/lib/diagnostics";
import type { AdminUser, Session } from "@/types/api";

type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

type AuthState = {
  status: AuthStatus;
  admin: AdminUser | null;
  error: string | null;
};

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    status: "loading",
    admin: null,
    error: null,
  });

  const checkSession = useCallback(async () => {
    let meStatus = 0;
    try {
      const session = await api.get<Session>("/auth/me", undefined);
      meStatus = 200;
      setCsrfToken(session.csrf_token);
      setState({ status: "authenticated", admin: session.admin, error: null });
    } catch (error) {
      if (error instanceof ApiError) meStatus = error.status;
      if (error instanceof ApiError && error.status === 401) {
        setCsrfToken(null);
        setState({ status: "anonymous", admin: null, error: null });
      } else {
        setState({
          status: "error",
          admin: null,
          error: errorMessage(error),
        });
      }
    }
    void reportPreviewSession({
      meStatus,
      hasDevToken: hasBearerToken(),
      attachedBearer: hasBearerToken(),
    });
  }, []);

  useEffect(() => {
    // Restore the development-preview token before the first session check so a
    // page reload keeps working when the browser blocks the session cookie.
    const stored = loadBearerToken();
    if (stored) setBearerToken(stored);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- session check on mount
    void checkSession();
    const onUnauthorized = () => {
      setCsrfToken(null);
      setBearerToken(null);
      setState({ status: "anonymous", admin: null, error: null });
    };
    window.addEventListener("nn:unauthorized", onUnauthorized);
    return () => window.removeEventListener("nn:unauthorized", onUnauthorized);
  }, [checkSession]);

  const login = useCallback(async (email: string, password: string) => {
    // Best effort: inside a third-party iframe the Storage Access API can unlock
    // cookies for this origin. It must run from the user gesture (this submit).
    try {
      await document.requestStorageAccess?.();
    } catch {
      // Denied or unsupported; the header fallback below still applies.
    }

    const session = await api.post<Session>("/auth/login", { email, password });
    setCsrfToken(session.csrf_token);
    setBearerToken(session.dev_session_token ?? null);
    const hadToken = Boolean(session.dev_session_token);

    // Prove that the new session actually works before leaving the login page.
    // Without this check a browser that refuses the preview cookie would render
    // the shell, fail every request and silently bounce back to the login form.
    try {
      await api.get<Session>("/auth/me");
    } catch {
      setCsrfToken(null);
      setBearerToken(null);
      void reportPreviewSession({
        meStatus: 401,
        hasDevToken: hadToken,
        attachedBearer: hadToken,
      });
      throw new ApiError(
        0,
        "session_not_persisted",
        "ورود پذیرفته شد اما نشست در این مرورگر ذخیره نشد. صفحه پیش نمایش را در یک تب جدید باز کنید یا کوکی ها را برای این سایت مجاز کنید.",
      );
    }
    setState({ status: "authenticated", admin: session.admin, error: null });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Revoking the local session is enough if the server call fails.
    }
    setCsrfToken(null);
    setBearerToken(null);
    setState({ status: "anonymous", admin: null, error: null });
    router.replace("/login");
  }, [router]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, refresh: checkSession }),
    [state, login, logout, checkSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
