"use client";

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;
    // Preview/staging builds can opt out so a rebuild never serves cached assets.
    if (process.env.NEXT_PUBLIC_SW_ENABLED === "0") return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // Registration is best effort; the app remains fully usable online.
      });
    };

    if (document.readyState === "complete") {
      register();
      return;
    }
    window.addEventListener("load", register, { once: true });
    return () => window.removeEventListener("load", register);
  }, []);

  return null;
}
