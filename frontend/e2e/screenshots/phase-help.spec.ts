/**
 * In-app help screenshots: the Help page (browse and search), an article,
 * no results, loading and error, and the global search's Help group, at
 * desktop, tablet and phone widths in light and dark mode.
 *
 *   SCREENSHOT_PHASE=help npx playwright test --project=screenshots
 */
import path from "node:path";

import { expect, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = process.env.SCREENSHOT_DIR ?? "../docs/screenshots/help";

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("help", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto("/help");
        await expect(page.getByRole("heading", { name: "Service", level: 2 })).toBeVisible();
        await shot(page, "help-browse");

        await page.getByRole("searchbox", { name: "Search help" }).fill("customer's hours went down");
        await expect(page.getByRole("list", { name: "Search results" })).toBeVisible();
        await shot(page, "help-search-results", false);

        await page.getByRole("searchbox", { name: "Search help" }).fill("zzqx wobblefrump");
        await expect(page.getByText(/Nothing found for/)).toBeVisible();
        await shot(page, "help-no-results", false);

        await page.goto("/help/work-orders");
        await expect(page.getByRole("heading", { name: "Work orders", level: 1 })).toBeVisible();
        await shot(page, "help-article");
        await page.goto("/help/work-orders#log-labor");
        await expect(page.getByRole("heading", { name: "Log labor" })).toBeInViewport();
        await shot(page, "help-article-jump-to-heading", false);

        await page.goto("/service/maintenance");
        await expect(page.getByRole("link", { name: /Help for this page/ })).toBeVisible();
        await shot(page, "help-button-in-header", false);
        await page.context().close();
      });

      test("help for sales and admin", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/help/quotes");
        await expect(page.getByRole("heading", { name: "Quotes", level: 1 })).toBeVisible();
        await shot(page, "help-article-sales");
        await page.context().close();
        const admin = await newPage(browser, viewport, theme, authFile("admin"));
        await admin.goto("/help/users-and-roles");
        await expect(admin.getByRole("heading", { name: "Users and roles", level: 1 })).toBeVisible();
        await shot(admin, "help-article-admin");
        await admin.context().close();
      });

      test("global search", async ({ browser }) => {
        test.skip(viewport === "phone", "the phone search is a dialog; covered by the search shots");
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/");
        await page.getByRole("combobox").fill("receive parts");
        await expect(page.getByText("Help", { exact: true })).toBeVisible();
        await shot(page, "global-search-help", false);
        await page.context().close();
      });

      test("phone search", async ({ browser }) => {
        test.skip(viewport !== "phone", "phone only");
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/");
        await page.getByRole("button", { name: "Search" }).click();
        await page.getByRole("dialog").getByRole("searchbox").fill("receive parts");
        await expect(page.getByRole("dialog").getByText("Help", { exact: true })).toBeVisible();
        await shot(page, "global-search-help", false);
        await page.context().close();
      });

      test("loading and error", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.route("**/api/v1/help", (route) => route.fulfill({ status: 500, json: { detail: "boom" } }));
        await page.goto("/help");
        await expect(page.getByText("We couldn't load Help.")).toBeVisible({ timeout: 15_000 });
        await shot(page, "help-error", false);
        await page.unroute("**/api/v1/help");
        await page.route("**/api/v1/help/work-orders", () => new Promise(() => {}));
        await page.goto("/help/work-orders");
        await expect(page.getByRole("status", { name: "Loading" })).toBeVisible();
        // The request never answers, so don't wait for the network to settle.
        await page.screenshot({ path: path.join(OUT, `help-article-loading-${viewport}-${theme}.png`), animations: "disabled" });
        await page.context().close();
      });
    });
  }
}
