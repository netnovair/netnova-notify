"use client";

import { CheckCircle2, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type Toast = { id: number; message: string; tone: "success" | "error" | "info" };
type ToastContextValue = {
  push: (message: string, tone?: Toast["tone"]) => void;
  notify: (message: string, tone?: Toast["tone"]) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: Toast["tone"] = "info") => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current.slice(-3), { id, message, tone }]);
      window.setTimeout(() => remove(id), tone === "error" ? 7000 : 4500);
    },
    [remove],
  );

  const value = useMemo(() => ({ push, notify: push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 bottom-20 z-[70] flex flex-col items-center gap-2 px-4 lg:bottom-6 lg:items-end lg:pe-6"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className={`pointer-events-auto flex w-full max-w-sm items-start gap-2 rounded-xl border px-3.5 py-2.5 text-xs leading-6 shadow-xl shadow-black/30 backdrop-blur ${
              toast.tone === "success"
                ? "border-success/40 bg-[#0d2b24] text-[#c8f5e5]"
                : toast.tone === "error"
                  ? "border-danger/40 bg-[#2c1116] text-[#ffd0d0]"
                  : "border-line bg-surface text-ink"
            }`}
          >
            {toast.tone === "success" ? (
              <CheckCircle2 size={15} className="mt-1 shrink-0 text-success" aria-hidden />
            ) : toast.tone === "error" ? (
              <XCircle size={15} className="mt-1 shrink-0 text-danger" aria-hidden />
            ) : null}
            <p className="flex-1">{toast.message}</p>
            <button
              type="button"
              onClick={() => remove(toast.id)}
              aria-label="بستن پیام"
              className="mt-0.5 rounded p-0.5 text-muted hover:text-ink"
            >
              <X size={13} aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
