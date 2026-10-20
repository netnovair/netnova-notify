export type ApiErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export class NetworkError extends Error {
  constructor(message = "ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی کنید.") {
    super(message);
    this.name = "NetworkError";
  }
}

const BASE_URL = "/api/v1";
const BEARER_STORAGE_KEY = "nn_dev_preview_session";
const BEARER_WINDOW_PREFIX = "nn_dev_session:";
/**
 * Some preview iframes block cookies, `sessionStorage` and `localStorage` at the
 * same time. `window.name` survives reloads and Fast Refresh inside the same tab
 * without being sent to any server, so it is used as the last development-only
 * fallback. It is never written in a production build.
 */
let csrfToken: string | null = null;
let bearerToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

/**
 * Development preview fallback: some browsers drop third-party cookies inside
 * the preview iframe. Only a preview host receives `dev_session_token` from the
 * API, so this token is never present in a normal or production session.
 */
export function setBearerToken(token: string | null) {
  bearerToken = token;
  if (typeof window === "undefined") return;
  try {
    if (token) {
      window.sessionStorage.setItem(BEARER_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(BEARER_STORAGE_KEY);
    }
  } catch {
    // Storage can be unavailable in private or blocked contexts; the in-memory
    // token and the window.name fallback below still cover the session.
  }
  try {
    if (token) {
      window.name = `${BEARER_WINDOW_PREFIX}${token}`;
    } else if (window.name.startsWith(BEARER_WINDOW_PREFIX)) {
      window.name = "";
    }
  } catch {
    // Assigning window.name is allowed in every real browser; ignore odd hosts.
  }
}

export function hasBearerToken(): boolean {
  if (!bearerToken) bearerToken = loadBearerToken();
  return Boolean(bearerToken);
}

export function loadBearerToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.sessionStorage.getItem(BEARER_STORAGE_KEY);
    if (stored) return stored;
  } catch {
    // Fall through to the window.name fallback.
  }
  try {
    if (window.name.startsWith(BEARER_WINDOW_PREFIX)) {
      return window.name.slice(BEARER_WINDOW_PREFIX.length) || null;
    }
  } catch {
    // Ignore an unreadable window.name.
  }
  return null;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  /** Skip the global 401 broadcast (used by the session check itself). */
  silentAuth?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  // Re-hydrate on every request: Fast Refresh re-executes this module and clears
  // the in-memory value, which used to make the panel silently drop the session.
  if (!bearerToken) {
    bearerToken = loadBearerToken();
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (bearerToken) {
    headers.Authorization = `Bearer ${bearerToken}`;
    // Some preview proxies strip the standard Authorization header, so the same
    // token travels in a custom header as well. The API accepts either one.
    headers["X-NN-Session"] = bearerToken;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (method !== "GET") {
    headers["X-CSRF-Token"] = csrfToken ?? "";
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new NetworkError();
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const body = (data ?? {}) as ApiErrorBody;
    const status = response.status;
    if (status === 401 && !options.silentAuth && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nn:unauthorized"));
    }
    throw new ApiError(
      status,
      body.error?.code ?? `http_${status}`,
      body.error?.message ?? "درخواست انجام نشد. لطفا دوباره تلاش کنید.",
      body.error?.details,
    );
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) =>
    request<T>(path, { method: "GET", signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "";
  }
  return "خطای غیرمنتظره رخ داد. لطفا دوباره تلاش کنید.";
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function queryString(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}
