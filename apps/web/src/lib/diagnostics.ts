/**
 * Development-only preview diagnostics.
 *
 * A hosted preview is rendered inside a cross-origin iframe, where browsers may
 * block cookies and every storage API at the same time. When the admin panel
 * logs in but cannot read data, the server log is the only place to see why.
 *
 * The report contains booleans, one HTTP status and the user agent. It never
 * contains a token, a cookie, a URL path or any operational data.
 */

const REPORTED_KEY = "nn_preview_report_sent";

function storageWorks(kind: "sessionStorage" | "localStorage"): boolean {
  try {
    const storage = window[kind];
    const probe = `nn-probe-${Date.now()}`;
    storage.setItem(probe, "1");
    storage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

export type PreviewReport = {
  meStatus: number;
  /** Did the login response itself contain a token? */
  hasDevToken: boolean;
  /** Was a token still present when the request header was built? */
  attachedBearer: boolean;
};

export async function reportPreviewSession(report: PreviewReport): Promise<void> {
  // Enabled for the hosted preview build only; a normal production build never
  // contains this flag and therefore never reports anything.
  if (process.env.NEXT_PUBLIC_PREVIEW_DIAGNOSTICS !== "1") return;
  if (typeof window === "undefined") return;
  try {
    // Only the first report of a page load; avoid spamming the log.
    if (window.sessionStorage.getItem(REPORTED_KEY) === "1") return;
    window.sessionStorage.setItem(REPORTED_KEY, "1");
  } catch {
    // Storage blocked: report anyway, that is exactly what we need to see.
  }

  const flags = {
    in_iframe: window.top !== window.self,
    // An opaque origin (sandboxed iframe without allow-same-origin) serializes as "null".
    opaque_origin: window.origin === "null" || location.origin === "null",
    secure_context: window.isSecureContext,
    cookies_enabled: navigator.cookieEnabled,
    session_storage: storageWorks("sessionStorage"),
    local_storage: storageWorks("localStorage"),
    window_name: Boolean(window.name),
    has_dev_token: report.hasDevToken,
    attached_bearer: report.attachedBearer,
    api_ok: report.meStatus === 200,
  };

  try {
    await fetch("/api/v1/diagnostics/client", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      cache: "no-store",
      body: JSON.stringify({
        flags,
        me_status: report.meStatus,
        user_agent: navigator.userAgent,
      }),
    });
  } catch {
    // Diagnostics must never break the app.
  }
}
