/**
 * Phase 4 screenshots: work orders, at desktop, tablet and phone widths in
 * light and dark mode, plus empty, loading and error states.
 *
 *   SCREENSHOT_PHASE=4 npx playwright test --project=screenshots
 */
import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(4);

async function workOrderId(page: Page, q: string): Promise<string> {
  const res = await page.request.get(`/api/v1/work-orders?scope=all&q=${encodeURIComponent(q)}`);
  const body = (await res.json()) as { results: { id: string }[] };
  const id = body.results[0]?.id;
  if (!id) throw new Error(`demo work order "${q}" not found; run seed_dev`);
  return id;
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("lists and dashboard", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto("/service");
        await expect(page.getByText(/Mast chatters/).filter({ visible: true }).first()).toBeVisible();
        await shot(page, "service-open");
        await page.getByRole("tab", { name: "Completed" }).click();
        await expect(page.getByText(/250-hour service/).filter({ visible: true }).first()).toBeVisible();
        await shot(page, "service-completed");
        await page.goto("/");
        await expect(page.getByRole("link", { name: /Open work orders/ })).toContainText(/\d/);
        await shot(page, "dashboard-service");
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("service"));
        await empty.route("**/api/v1/work-orders?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.goto("/service");
        await expect(empty.getByText("No open work orders")).toBeVisible();
        await shot(empty, "service-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("service"));
        await slow.route("**/api/v1/work-orders?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/service");
        await expect(slow.getByRole("status").filter({ hasText: "Loading" }).first()).toBeAttached();
        await slow.screenshot({ path: `${OUT}/service-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("service"));
        await broken.route("**/api/v1/work-orders?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/service");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "service-error");
        await broken.context().close();
      });

      test("new work order", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto("/service/new");
        await expect(page.getByRole("heading", { name: "New work order", level: 1 })).toBeVisible();
        await shot(page, "work-order-new");
        await page.getByRole("button", { name: "Open work order" }).click();
        await expect(page.getByText("Pick the unit.")).toBeVisible();
        await shot(page, "work-order-new-errors");
        await page.getByLabel("Unit", { exact: true }).fill("hyundai");
        await expect(page.getByRole("option").first()).toBeVisible();
        await shot(page, "work-order-new-unit-search", false);
        await page.getByRole("option", { name: /70D-9/ }).click();
        await page.getByLabel("What's wrong (complaint)").fill("Steering is stiff at low speed; customer says it's getting worse.");
        await page.getByLabel("Where").selectOption("field");
        await page.getByLabel("Contact on site (optional)").fill("Mike, 207-555-0144");
        await shot(page, "work-order-new-filled");
        await page.context().close();
      });

      test("work order page", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto(`/service/${await workOrderId(page, "Mast chatters")}`);
        await expect(page.getByRole("list", { name: "Labor lines" })).toBeVisible();
        await shot(page, "work-order-in-progress");
        await page.getByRole("button", { name: "Put on hold" }).click();
        await page.getByRole("dialog").getByLabel("Waiting for").fill("Mast rollers from Hyundai");
        await shot(page, "work-order-hold-dialog", false);
        await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
        await page.getByLabel("Cause").fill("Worn mast rollers on the inner rail. Rollers measured 0.06 in under spec.");
        await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
        await shot(page, "work-order-unsaved", false);

        await page.goto(`/service/${await workOrderId(page, "Hydraulic leak")}`);
        await expect(page.getByText("On hold:")).toBeVisible();
        await shot(page, "work-order-on-hold");
        await page.goto(`/service/${await workOrderId(page, "250-hour")}`);
        await expect(page.getByRole("button", { name: "Reopen" })).toBeVisible();
        await shot(page, "work-order-completed");

        const unit = await (await page.request.get("/api/v1/units?scope=all&q=HHKHFV30K00057")).json() as { results: { id: string }[] };
        await page.goto(`/units/${unit.results[0]?.id}#service`);
        await expect(page.getByRole("list", { name: "Work orders for this unit" })).toBeVisible();
        await page.locator("#service").scrollIntoViewIfNeeded();
        await shot(page, "unit-service-history", false);
        await page.context().close();

        const sales = await newPage(browser, viewport, theme, authFile("sales"));
        await sales.goto(`/service/${await workOrderId(sales, "Mast chatters")}`);
        await expect(sales.getByRole("list", { name: "Labor lines" })).toBeVisible();
        await shot(sales, "work-order-read-only");
        await sales.context().close();

        const missing = await newPage(browser, viewport, theme, authFile("service"));
        await missing.goto("/service/00000000-0000-0000-0000-000000000000");
        await expect(missing.getByText("Work order not found")).toBeVisible();
        await shot(missing, "work-order-not-found");
        await missing.context().close();
      });
    });
  }
}
