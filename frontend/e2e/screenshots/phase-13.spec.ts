/**
 * Phase 13 screenshots: the saved copy on devices (offline), the offline
 * banner, "can't reach the system" with the saved copy, and Admin > Paper
 * backup, at desktop, tablet and phone widths in light and dark mode, plus
 * empty, failed and loading states.
 *
 *   SCREENSHOT_PHASE=13 npx playwright test --project=screenshots
 */
import { expect, test } from "@playwright/test";

import { authFile, savedCopyReady } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(13);

test.beforeAll(async ({ browser }) => {
  // One paper backup, so the admin page has files to show.
  const page = await newPage(browser, "desktop", "light", authFile("admin"));
  const csrf = (await page.context().cookies()).find((c) => c.name === "mmh_csrftoken")?.value ?? "";
  await page.goto("/");
  const res = await page.request.post("/api/v1/admin/paper-backups", { headers: { "X-CSRFToken": csrf, Referer: "http://localhost:8000" } });
  expect(res.status()).toBe(201);
  await page.context().close();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("offline", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto("/");
        await savedCopyReady(page);
        await expect(page.getByRole("region", { name: "At a glance" }).getByRole("link").first()).toBeVisible();
        await page.context().setOffline(true);
        await expect(page.getByText("You're offline.")).toBeVisible();
        await shot(page, "offline-banner", false);

        await page.reload();
        await expect(page.getByText("Can't reach the system")).toBeVisible();
        await shot(page, "cant-reach-with-saved-copy");

        await page.getByRole("link", { name: /Open the saved copy/ }).click();
        await expect(page.getByRole("heading", { name: "Units (saved copy)" })).toBeVisible();
        await shot(page, "offline-units");
        await page.getByRole("tab", { name: /Our stock/ }).click();
        await shot(page, "offline-units-stock");
        await page.getByRole("searchbox", { name: "Search saved units" }).fill("zzzz-none");
        await expect(page.getByText("No saved units match")).toBeVisible();
        await shot(page, "offline-units-no-match", false);
        await page.goto("/offline");
        await page.getByRole("searchbox", { name: "Search saved units" }).fill("HHKHHN04P00123");
        await page.getByRole("list", { name: "Saved units" }).getByRole("link").first().click();
        await expect(page.getByRole("heading", { name: "Components" })).toBeVisible();
        await shot(page, "offline-unit-spec-card");
        await page.context().close();

        const fresh = await newPage(browser, viewport, theme);
        await fresh.goto("/offline");
        await expect(fresh.getByText("Nothing saved on this device")).toBeVisible();
        await shot(fresh, "offline-nothing-saved");
        await fresh.context().close();
      });

      test("paper backup", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/admin/paper-backup");
        await expect(page.getByRole("list", { name: "Paper backup files" })).toContainText("paper-backup.zip");
        await shot(page, "paper-backup");
        await page.goto("/");
        await expect(page.locator("text=Paper backup >> visible=true").last()).toBeVisible();
        await page.getByText("System health").scrollIntoViewIfNeeded();
        await shot(page, "dashboard-health-paper-backup", false);
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("admin"));
        await empty.route("**/api/v1/admin/paper-backups", (route) => route.fulfill({ json: { results: [] } }));
        await empty.goto("/admin/paper-backup");
        await expect(empty.getByText("No paper backup yet")).toBeVisible();
        await shot(empty, "paper-backup-empty");
        await empty.context().close();

        const failed = await newPage(browser, viewport, theme, authFile("admin"));
        await failed.route("**/api/v1/admin/paper-backups", async (route) => {
          const real = (await (await route.fetch()).json()) as { results: Record<string, unknown>[] };
          const ok = real.results[0] ?? {};
          await route.fulfill({
            json: {
              results: [
                { ...ok, id: "x", status: "failed", status_label: "Failed", error: "Couldn't reach backup storage", files: [] },
                ...real.results,
              ],
            },
          });
        });
        await failed.goto("/admin/paper-backup");
        await expect(failed.getByText(/failed: Couldn't reach backup storage/)).toBeVisible();
        await shot(failed, "paper-backup-failed");
        await failed.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("admin"));
        await slow.route("**/api/v1/admin/paper-backups", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/admin/paper-backup");
        await expect(slow.getByRole("heading", { name: "Paper backup" })).toBeVisible();
        await slow.screenshot({ path: `${OUT}/paper-backup-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();
      });
    });
  }
}
