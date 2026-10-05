/**
 * Small fetch wrapper for the Django API (same origin, session cookie + CSRF).
 */

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string[]>;

  constructor(status: number, code: string, detail: string, fields: Record<string, string[]> = {}) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }

  fieldError(name: string): string | undefined {
    return this.fields[name]?.[0];
  }
}

const CSRF_COOKIE = "mmh_csrftoken";

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

async function ensureCsrf(): Promise<string> {
  let token = readCookie(CSRF_COOKIE);
  if (!token) {
    await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
    token = readCookie(CSRF_COOKIE);
  }
  return token ?? "";
}

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface ErrorBody {
  code?: string;
  detail?: string;
  fields?: Record<string, string[] | string>;
}

function normalizeFields(fields: ErrorBody["fields"]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(fields ?? {})) {
    out[key] = Array.isArray(value) ? value.map(String) : [value];
  }
  return out;
}

export async function api<T>(path: string, options: { method?: Method; body?: unknown } = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    headers["X-CSRFToken"] = await ensureCsrf();
  }
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection and try again.");
  }

  if (response.status === 204) return undefined as T;
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
    const body = (data ?? {}) as ErrorBody;
    throw new ApiError(
      response.status,
      body.code ?? `http_${response.status}`,
      body.detail ?? "Something went wrong. Please try again.",
      normalizeFields(body.fields),
    );
  }
  return data as T;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
