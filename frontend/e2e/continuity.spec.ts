import { expect, type Page, test } from "@playwright/test";

import { apiLogin, authFile, USERS } from "./helpers";

const BASE = "http://localhost:8000";

/** Wait until the service worker controls the page and the saved copy is on the device. */
async function savedCopyReady(page: Page): Promise<number> {
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

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("the app opens offline and shows the saved copy of units", async ({ page, context }) => {
    await page.goto("/");
    const saved = await savedCopyReady(page);

    await context.setOffline(true);
    // The device has no network: a banner says so and points to the saved copy.
    await expect(page.getByText("You're offline.")).toBeVisible();
    await page.reload();
    // The app itself still opens (from the service worker), but can't reach the system.
    await expect(page.getByText("Can't reach the system")).toBeVisible();
    await page.getByRole("link", { name: `Open the saved copy (${saved} units)` }).click();

    await expect(page.getByRole("heading", { name: "Units (saved copy)" })).toBeVisible();
    await expect(page.getByText("This device is offline.")).toBeVisible();
    await page.getByRole("searchbox", { name: "Search saved units" }).fill("hhkhfv30k00057");
    const list = page.getByRole("list", { name: "Saved units" });
    await expect(list.getByRole("listitem")).toHaveCount(1);
    await list.getByRole("link").click();
    await expect(page.getByText("HHKHFV30K00057").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Components" })).toBeVisible();
    await expect(page.getByText("Our cost")).toHaveCount(0);

    await context.setOffline(false);
    await page.getByRole("link", { name: "Try the live system" }).click();
    await expect(page.getByRole("region", { name: "At a glance" })).toBeVisible();
  });
});

test("signing out wipes the saved copy", async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE });
  await apiLogin(context.request, BASE, USERS.parts);
  const page = await context.newPage();
  await page.goto("/");
  await savedCopyReady(page);
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/offline");
  await expect(page.getByText("Nothing saved on this device")).toBeVisible();
  await context.close();
});

test.describe("as admin", () => {
  test.use({ storageState: authFile("admin") });

  test("makes a paper backup and opens the files", async ({ page }) => {
    await page.goto("/admin/paper-backup");
    await page.getByRole("button", { name: "Make one now" }).click();
    await expect(page.getByText("A fresh paper backup is ready.")).toBeVisible({ timeout: 30_000 });
    const files = page.getByRole("list", { name: "Paper backup files" });
    await expect(files).toContainText("Open work orders, printed in full");
    await expect(files).toContainText("paper-backup.zip");
    const href = await files.getByRole("link", { name: "Open to print" }).first().getAttribute("href");
    const pdf = await page.request.get(href ?? "");
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toBe("application/pdf");
    await page.goto("/");
    await expect(page.getByText("Paper backup", { exact: true })).toBeVisible();
  });
});
