import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  NetworkError,
  api,
  errorMessage,
  queryString,
  setBearerToken,
  setCsrfToken,
} from "@/lib/api";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  setCsrfToken(null);
  setBearerToken(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  it("sends the CSRF header on mutations and keeps credentials", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    setCsrfToken("csrf-123");
    await api.post("/projects", { name: "x" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/projects");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("same-origin");
    expect(init.cache).toBe("no-store");
    expect(init.headers["X-CSRF-Token"]).toBe("csrf-123");
    expect(init.body).toBe(JSON.stringify({ name: "x" }));
  });

  it("sends the development preview bearer token on every request", async () => {
    fetchMock.mockImplementation(() => jsonResponse({ items: [] }));
    setBearerToken("preview-session-token");
    await api.get("/dashboard");
    await api.post("/projects", { name: "x" });
    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers.Authorization).toBe("Bearer preview-session-token");
    }
  });

  it("re-hydrates the token after a Fast Refresh wiped the in-memory value", async () => {
    fetchMock.mockImplementation(() => jsonResponse({ items: [] }));
    setBearerToken("survives-refresh");
    // Simulate a module re-execution: in-memory state is gone but storage remains.
    vi.resetModules();
    const reloaded = await import("@/lib/api");
    reloaded.setCsrfToken(null);
    await reloaded.api.get("/dashboard");
    const [, init] = fetchMock.mock.calls.at(-1)!;
    expect(init.headers.Authorization).toBe("Bearer survives-refresh");
  });

  it("sends the session token in a custom header as well as Bearer", async () => {
    fetchMock.mockImplementation(() => jsonResponse({ items: [] }));
    setBearerToken("preview-session-token");
    await api.get("/dashboard");
    const [, init] = fetchMock.mock.calls.at(-1)!;
    expect(init.headers.Authorization).toBe("Bearer preview-session-token");
    expect(init.headers["X-NN-Session"]).toBe("preview-session-token");
  });

  it("does not add CSRF headers to reads", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [] }));
    await api.get("/projects");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("parses standard API errors", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "forbidden", message: "دسترسی مجاز نیست." } }, 403),
    );
    await expect(api.get("/dashboard")).rejects.toMatchObject({
      status: 403,
      code: "forbidden",
      message: "دسترسی مجاز نیست.",
    });
  });

  it("broadcasts unauthorized responses", async () => {
    const listener = vi.fn();
    window.addEventListener("nn:unauthorized", listener);
    fetchMock.mockResolvedValue(
      jsonResponse({ error: { code: "unauthorized", message: "وارد شوید." } }, 401),
    );
    await expect(api.get("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("nn:unauthorized", listener);
  });

  it("maps network failures to a Persian message", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(api.get("/projects")).rejects.toBeInstanceOf(NetworkError);
    expect(errorMessage(new NetworkError())).toContain("ارتباط با سرور");
  });

  it("builds query strings without empty values", () => {
    expect(queryString({ search: "a", page: 2, empty: "", missing: null })).toBe(
      "?search=a&page=2",
    );
    expect(queryString({})).toBe("");
  });
});
