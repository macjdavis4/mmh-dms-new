/**
 * Phase 12 screenshots: the dashboard for each role, the reports list and
 * each report, at desktop, tablet and phone widths in light and dark mode,
 * plus empty, loading, error and not-allowed states.
 *
 *   SCREENSHOT_PHASE=12 npx playwright test --project=screenshots
 */
import { expect, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(12);

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("dashboards", async ({ browser }) => {
        for (const role of ["admin", "sales", "service", "parts", "viewer"] as const) {
          const page = await newPage(browser, viewport, theme, authFile(role));
          await page.goto("/");
          await expect(page.getByRole("region", { name: "At a glance" }).getByRole("link").first()).toBeVisible();
          await shot(page, `dashboard-${role}`);
          await page.context().close();
        }
        const slow = await newPage(browser, viewport, theme, authFile("parts"));
        await slow.route("**/api/v1/dashboard", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/");
        await expect(slow.getByRole("region", { name: "At a glance" }).locator("[aria-busy=true]")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/dashboard-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();
      });

      test("reports", async ({ browser }) => {
        const sales = await newPage(browser, viewport, theme, authFile("sales"));
        await sales.goto("/reports");
        await expect(sales.getByRole("link", { name: /Units sold/ })).toBeVisible();
        await shot(sales, "reports");
        await sales.goto("/reports/units-sold?from=2026-03-01&to=2026-03-31");
        await expect(sales.locator("text=Bangor Building Supply >> visible=true").first()).toBeVisible();
        await shot(sales, "report-units-sold");
        await sales.goto("/reports/units-in-stock");
        await expect(sales.locator("text=In stock since >> visible=true").or(sales.locator("text=Days >> visible=true")).first()).toBeVisible();
        await shot(sales, "report-units-in-stock");
        await sales.context().close();

        const parts = await newPage(browser, viewport, theme, authFile("parts"));
        await parts.goto("/reports/parts-valuation");
        await expect(parts.locator("text=31N4-01050 >> visible=true").first()).toBeVisible();
        await shot(parts, "report-parts-valuation");
        await parts.goto("/reports/parts-received");
        await expect(parts.locator("text=HMA-558790 >> visible=true").first()).toBeVisible();
        await shot(parts, "report-parts-received");
        await parts.goto("/reports/parts-received?period=last_year");
        await expect(parts.getByText("Nothing in this period")).toBeVisible();
        await shot(parts, "report-empty");
        await parts.context().close();

        const service = await newPage(browser, viewport, theme, authFile("service"));
        await service.goto("/reports/labor-by-mechanic?period=last_12_months");
        await expect(service.locator("text=Sam Wrench >> visible=true").first()).toBeVisible();
        await shot(service, "report-labor-by-mechanic");
        await service.goto("/reports/work-orders-completed?period=last_12_months");
        await expect(service.locator("text=/WO-\\d+/ >> visible=true").first()).toBeVisible();
        await shot(service, "report-work-orders-completed");
        await service.goto("/reports/parts-used");
        await expect(service.locator("text=BL-634 >> visible=true").first()).toBeVisible();
        await shot(service, "report-parts-used-mechanic");
        await service.goto("/reports/parts-valuation");
        await expect(service.getByText("This report isn't available to you")).toBeVisible();
        await shot(service, "report-not-allowed");
        await service.context().close();

        const custom = await newPage(browser, viewport, theme, authFile("admin"));
        await custom.goto("/reports/parts-used");
        await custom.getByLabel("Dates").selectOption("custom");
        await expect(custom.getByLabel("From", { exact: true })).toBeVisible();
        await shot(custom, "report-pick-dates");
        await custom.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("admin"));
        await slow.route("**/api/v1/reports/parts-used?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/reports/parts-used");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/report-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("admin"));
        await broken.route("**/api/v1/reports/parts-used?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/reports/parts-used");
        await expect(broken.getByText("We couldn't run this report.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "report-error");
        await broken.context().close();
      });
    });
  }
}
