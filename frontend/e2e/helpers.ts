import { createHmac } from "node:crypto";

import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = "Forklift-Demo-2026!";
export const DEMO_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";

export const USERS = {
  admin: "admin@mmh.test",
  admin2: "admin2@mmh.test",
  newadmin: "newadmin@mmh.test",
  sales: "sales@mmh.test",
  service: "service@mmh.test",
  parts: "parts@mmh.test",
  viewer: "viewer@mmh.test",
} as const;

function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.replace(/[\s=]/g, "").toUpperCase();
  let bits = "";
  for (const char of clean) {
    const v = alphabet.indexOf(char);
    if (v < 0) throw new Error(`bad base32 char ${char}`);
    bits += v.toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238 TOTP (SHA-1, 30 s, 6 digits). `stepOffset` 1 = the next code. */
export function totp(secret: string, stepOffset = 0, now = Date.now()): string {
  const counter = Math.floor(now / 1000 / 30) + stepOffset;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac("sha1", base32Decode(secret)).update(buf).digest();
  const offset = (hmac[hmac.length - 1] ?? 0) & 0xf;
  const code = ((hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).toString();
  return code.padStart(6, "0");
}

async function csrf(request: APIRequestContext, baseURL: string): Promise<string> {
  await request.get("/api/v1/auth/csrf");
  const state = await request.storageState();
  const host = new URL(baseURL).hostname;
  return state.cookies.find((c) => c.name === "mmh_csrftoken" && c.domain.includes(host))?.value ?? "";
}

/** Sign in through the API (fast). Handles the 2FA step for the demo admins. */
export async function apiLogin(request: APIRequestContext, baseURL: string, email: string): Promise<void> {
  const token = await csrf(request, baseURL);
  const res = await request.post("/api/v1/auth/login", {
    data: { email, password: PASSWORD },
    headers: { "X-CSRFToken": token, Referer: baseURL },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { status: string };
  if (body.status !== "otp_required") return;
  // A code can only be used once; if this window's code was just used, the
  // next window's code is also accepted (one step of clock drift is allowed).
  for (const offset of [0, 1]) {
    const verify = await request.post("/api/v1/auth/login/verify", {
      data: { code: totp(DEMO_TOTP_SECRET, offset) },
      headers: { "X-CSRFToken": await csrf(request, baseURL), Referer: baseURL },
    });
    if (verify.ok()) return;
    await new Promise((r) => setTimeout(r, 1200)); // django-otp backs off briefly after a miss
  }
  throw new Error(`2FA login failed for ${email}`);
}

export function authFile(role: keyof typeof USERS): string {
  return `e2e/.auth/${role}.json`;
}

/** Collect Content-Security-Policy violations and uncaught errors on a page. */
export function watchConsole(page: Page): string[] {
  const problems: string[] = [];
  page.on("console", (msg) => {
    const text = msg.text();
    if (msg.type() === "error" && /Content Security Policy|Refused to/i.test(text)) problems.push(text);
  });
  page.on("pageerror", (err) => problems.push(err.message));
  return problems;
}

/** Wait until the service worker controls the page and the saved copy is on the device. */
export async function savedCopyReady(page: Page): Promise<number> {
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // The first visit installs the service worker; a reload puts the page under its control.
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  const count = async () =>
    page.evaluate(
      () =>
        new Promise<number>((resolve) => {
          const req = indexedDB.open("mmh-offline", 1);
          req.onupgradeneeded = () => req.result.createObjectStore("packs");
          req.onsuccess = () => {
            const tx = req.result.transaction("packs", "readonly");
            const get = tx.objectStore("packs").get("units");
            get.onsuccess = () => resolve((get.result as { units?: unknown[] } | undefined)?.units?.length ?? 0);
            get.onerror = () => resolve(0);
          };
          req.onerror = () => resolve(0);
        }),
    );
  await expect.poll(count, { timeout: 15_000 }).toBeGreaterThan(0);
  return count();
}

