/**
 * Security audit screenshots: the "Reset two-factor" confirmation and the
 * two-factor notice admins see on the dashboard, at desktop, tablet and
 * phone widths in light and dark mode.
 *
 *   SCREENSHOT_PHASE=security SCREENSHOT_DIR=../docs/screenshots/security-audit \
 *     npx playwright test --project=screenshots
 */
import { expect, test } from "@playwright/test";

import { authFile, salesUserWithTwoFactor } from "../helpers";
import { newPage, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = process.env.SCREENSHOT_DIR ?? "../docs/screenshots/security-audit";
let quinn = "";

test.beforeAll(async ({ browser, playwright, baseURL }) => {
  const url = baseURL ?? "";
  const page = await newPage(browser, "desktop", "light", authFile("admin"));
  await page.goto("/");
  const jar = { cookies: [], origins: [] };
  // Quinn keeps two-factor: the dialog is opened and cancelled for each shot.
  const q = await playwright.request.newContext({
    baseURL: url,
    storageState: jar,
  });
  quinn = await salesUserWithTwoFactor(page.request, q, url, {
    first: "Quinn",
    last: "Phoned",
  });
  await q.dispose();
  // Riley's two-factor is reset once, so the dashboard has a notice.
  const r = await playwright.request.newContext({
    baseURL: url,
    storageState: jar,
  });
  const riley = await salesUserWithTwoFactor(page.request, r, url, {
    first: "Riley",
    last: "Lostphone",
  });
  await r.dispose();
  const list = (await (
    await page.request.get(`/api/v1/admin/users?q=${encodeURIComponent(riley)}`)
  ).json()) as {
    results: { id: string }[];
  };
  const csrf =
    (await page.context().cookies()).find((c) => c.name === "mmh_csrftoken")
      ?.value ?? "";
  const reset = await page.request.post(
    `/api/v1/admin/users/${list.results[0]?.id}/reset-2fa`,
    {
      data: { confirmed: "in_person" },
      headers: { "X-CSRFToken": csrf, Referer: url },
    },
  );
  expect(reset.ok(), await reset.text()).toBeTruthy();
  await page.context().close();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test(`${viewport} ${theme}`, async ({ browser }) => {
      const shot = shooter(OUT, viewport, theme);
      const page = await newPage(browser, viewport, theme, authFile("admin"));
      await page.goto(`/admin/users`);
      await page
        .locator("tr, li")
        .filter({ hasText: quinn })
        .getByRole("button", { name: /Actions for/ })
        .click();
      await page.getByRole("menuitem", { name: "Reset two-factor" }).click();
      const dialog = page.getByRole("alertdialog");
      await expect(dialog).toBeVisible();
      await shot(page, "reset-2fa-confirm-empty", false);
      await dialog
        .getByLabel("I called them back on a number we already had")
        .check();
      await shot(page, "reset-2fa-confirm-filled", false);
      await dialog.getByRole("button", { name: "Cancel" }).click();

      await page.goto("/");
      const notice = page.getByText("Two-factor changes (last 2 weeks)");
      await expect(notice).toBeVisible();
      await shot(page, "dashboard-2fa-notice");
      await page.context().close();
    });
  }
}
