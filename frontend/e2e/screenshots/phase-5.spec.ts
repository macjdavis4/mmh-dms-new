/**
 * Phase 5 screenshots: planned maintenance, at desktop, tablet and phone
 * widths in light and dark mode, plus empty, loading and error states.
 *
 *   SCREENSHOT_PHASE=5 npx playwright test --project=screenshots
 */
import { type APIRequestContext, expect, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(5);
const BASE = "http://localhost:8000";
let planWorkOrder = "";
let unitId = "";

async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get("/api/v1/auth/csrf");
  const cookie = (await request.storageState()).cookies.find((c) => c.name === "mmh_csrftoken");
  return { "X-CSRFToken": cookie?.value ?? "", Referer: BASE };
}

test.beforeAll(async ({ playwright }) => {
  const request = await playwright.request.newContext({ baseURL: BASE, storageState: authFile("service") });
  const units = (await (await request.get("/api/v1/units?scope=all&q=HHKHFV30K00057")).json()) as { results: { id: string }[] };
  unitId = units.results[0]?.id ?? "";
  // A work order already made from one plan, so the list shows both kinds of row.
  const due = (await (await request.get("/api/v1/maintenance-plans/due")).json()) as {
    results: { id: string; name: string; status: { open_work_order: { id: string } | null } }[];
  };
  const battery = due.results.find((p) => p.name === "Battery and charger check");
  if (battery?.status.open_work_order) {
    planWorkOrder = battery.status.open_work_order.id;
  } else if (battery) {
    const res = await request.post(`/api/v1/maintenance-plans/${battery.id}/work-order`, { headers: await csrfHeaders(request) });
    expect(res.ok(), await res.text()).toBeTruthy();
    planWorkOrder = ((await res.json()) as { id: string }).id;
  }
  await request.dispose();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("maintenance due", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto("/service/maintenance");
        await expect(page.getByRole("list", { name: "Maintenance due" })).toBeVisible();
        await shot(page, "maintenance-due");
        await page.getByLabel("Show plans that aren't due").check();
        await expect(page.getByRole("heading", { name: "All plans" })).toBeVisible();
        await expect(page.getByText("500-hour service")).toBeVisible();
        await shot(page, "maintenance-all");
        await page.goto("/");
        await expect(page.getByRole("link", { name: /PM due in 30 days/ })).toContainText(/\d/);
        await shot(page, "dashboard-service");
        await page.goto(`/service/${planWorkOrder}`);
        await expect(page.getByText("(Battery and charger check)")).toBeVisible();
        await shot(page, "work-order-from-plan");
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("service"));
        await empty.route("**/api/v1/maintenance-plans/due*", (route) => route.fulfill({ json: { counts: { overdue: 0, due_soon: 0 }, results: [] } }));
        await empty.goto("/service/maintenance");
        await expect(empty.getByText("Nothing due")).toBeVisible();
        await shot(empty, "maintenance-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("service"));
        await slow.route("**/api/v1/maintenance-plans/due*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/service/maintenance");
        await expect(slow.getByRole("status", { name: "Loading" })).toBeAttached();
        await slow.screenshot({ path: `${OUT}/maintenance-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("service"));
        await broken.route("**/api/v1/maintenance-plans/due*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/service/maintenance");
        await expect(broken.getByText("We couldn't load maintenance plans.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "maintenance-error");
        await broken.context().close();
      });

      test("plans on the unit page", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        await page.goto(`/units/${unitId}`);
        const plans = page.getByRole("list", { name: "Maintenance plans" });
        await expect(plans).toBeVisible();
        await page.locator("#maintenance").scrollIntoViewIfNeeded();
        await shot(page, "unit-maintenance", false);

        await page.getByRole("button", { name: "Add plan" }).click();
        await page.getByRole("dialog").getByRole("button", { name: "500-hour service" }).click();
        await shot(page, "plan-dialog-new", false);
        await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

        await page.getByRole("button", { name: "Actions for 250-hour service" }).click();
        await page.getByRole("menuitem", { name: "Edit" }).click();
        await expect(page.getByRole("dialog").getByLabel("Name")).toHaveValue("250-hour service");
        await shot(page, "plan-dialog-edit", false);
        await page.context().close();
      });
    });
  }
}
