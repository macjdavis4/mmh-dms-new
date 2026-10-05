import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi } from "@/test/utils";

import { api, ApiError, readCookie } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "mmh_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("api", () => {
  it("returns parsed JSON", async () => {
    mockApi(() => ({ body: { ok: true } }));
    await expect(api<{ ok: boolean }>("/api/v1/x")).resolves.toEqual({ ok: true });
  });

  it("sends the CSRF token on writes", async () => {
    document.cookie = "mmh_csrftoken=abc123";
    const spy = mockApi(() => ({ status: 204 }));
    await api("/api/v1/auth/logout", { method: "POST" });
    const init = spy.mock.calls[0]?.[1];
    expect((init?.headers as Record<string, string>)["X-CSRFToken"]).toBe("abc123");
    expect(init?.credentials).toBe("same-origin");
  });

  it("fetches a CSRF cookie first when missing", async () => {
    const spy = mockApi((url) => {
      if (url === "/api/v1/auth/csrf") document.cookie = "mmh_csrftoken=fresh";
      return { status: 204 };
    });
    await api("/api/v1/thing", { method: "PATCH", body: { a: 1 } });
    expect(spy.mock.calls[0]?.[0]).toBe("/api/v1/auth/csrf");
    expect((spy.mock.calls[1]?.[1]?.headers as Record<string, string>)["X-CSRFToken"]).toBe("fresh");
  });

  it("turns error responses into ApiError with field messages", async () => {
    mockApi(() => ({
      status: 400,
      body: { code: "invalid", detail: "Please fix the highlighted fields.", fields: { email: ["Taken."] } },
    }));
    const err = await api("/api/v1/admin/users", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(400);
    expect((err as ApiError).fieldError("email")).toBe("Taken.");
  });

  it("reports network failures plainly", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("offline"))));
    await expect(api("/api/v1/x")).rejects.toMatchObject({ code: "network", status: 0 });
  });

  it("reads cookies", () => {
    document.cookie = "other=1";
    document.cookie = "mmh_csrftoken=t%20k";
    expect(readCookie("mmh_csrftoken")).toBe("t k");
    expect(readCookie("missing")).toBeNull();
  });
});
