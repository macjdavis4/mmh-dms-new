/**
 * Phase 2 screenshots: customers and forklift units, at desktop, tablet and
 * phone widths in light and dark mode, plus empty, loading and error states.
 *
 *   SCREENSHOT_PHASE=2 npx playwright test --project=screenshots
 */
import { type Browser, expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Theme, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(2);

async function unitId(page: Page, serial: string): Promise<string> {
  const res = await page.request.get(`/api/v1/units?scope=all&q=${encodeURIComponent(serial)}`);
  const body = (await res.json()) as { results: { id: string }[] };
  const id = body.results[0]?.id;
  if (!id) throw new Error(`demo unit ${serial} not found; run seed_dev`);
  return id;
}

async function customerId(page: Page, name: string): Promise<string> {
  const res = await page.request.get(`/api/v1/customers?q=${encodeURIComponent(name)}`);
  const body = (await res.json()) as { results: { id: string }[] };
  const id = body.results[0]?.id;
  if (!id) throw new Error(`demo customer ${name} not found; run seed_dev`);
  return id;
}

/** A page whose list request never answers (loading) or fails (error). */
async function stateShots(
  browser: Browser,
  viewport: Viewport,
  theme: Theme,
  url: string,
  apiGlob: string,
  name: string,
  errorText: RegExp,
) {
  const shot = shooter(OUT, viewport, theme);
  const slow = await newPage(browser, viewport, theme, authFile("admin"));
  await slow.route(apiGlob, async () => {
    await new Promise(() => undefined);
  });
  await slow.goto(url);
  await expect(slow.getByRole("status").filter({ hasText: "Loading" }).or(slow.getByRole("status", { name: "Loading" })).first()).toBeAttached();
  await slow.screenshot({ path: `${OUT}/${name}-loading-${viewport}-${theme}.png`, animations: "disabled" });
  await slow.context().close();

  const broken = await newPage(browser, viewport, theme, authFile("admin"));
  await broken.route(apiGlob, (route) => route.fulfill({ status: 500, body: "" }));
  await broken.goto(url);
  await expect(broken.getByText(errorText).first()).toBeVisible({ timeout: 15_000 });
  await shot(broken, `${name}-error`);
  await broken.context().close();
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);
      const narrow = viewport !== "desktop";

      test("dashboard and global search", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/");
        await expect(page.getByRole("link", { name: /Units in stock/ })).toContainText(/\d/);
        await shot(page, "dashboard-sales");

        if (viewport === "phone") {
          await page.getByRole("button", { name: "Search", exact: true }).click();
          await page.getByRole("dialog").getByRole("searchbox").fill("hyundai 35");
        } else {
          await page.getByRole("combobox").fill("hyundai 35");
        }
        await expect(page.getByRole("link", { name: /Hyundai 35LN-9A/ }).filter({ visible: true }).first()).toBeVisible();
        await shot(page, "global-search-results", false);
        await page.context().close();
      });

      test("customers", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/customers");
        await expect(page.getByText("Penobscot Paper Co.").filter({ visible: true }).first()).toBeVisible();
        await shot(page, "customers");

        await page.locator("#customer-search").fill("nobody-by-this-name");
        await expect(page.getByText("No customers match")).toBeVisible();
        await shot(page, "customers-empty");
        await page.locator("#customer-search").fill("");

        await page.getByRole("button", { name: "Add customer" }).first().click();
        const dialog = page.getByRole("dialog");
        await dialog.getByRole("button", { name: "Add customer" }).click();
        await expect(dialog.getByText(/Enter/).first()).toBeVisible();
        await shot(page, "customer-form-errors", false);
        await dialog.getByLabel("Name").fill("Moosehead Marine");
        await dialog.getByLabel("Account number (optional)").fill("MM-2001");
        await dialog.getByLabel("Phone").fill("207-555-0170");
        await dialog.getByLabel("Email").fill("office@mooseheadmarine.example");
        await shot(page, "customer-form-filled", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        await page.goto(`/customers/${await customerId(page, "Penobscot Paper")}`);
        await expect(page.getByRole("heading", { name: "Penobscot Paper Co.", level: 1 })).toBeVisible();
        await shot(page, "customer-detail");

        await page.getByRole("button", { name: "Add contact" }).click();
        await page.getByRole("dialog").getByLabel("First name").fill("Robin");
        await page.getByRole("dialog").getByLabel("Last name").fill("Pelletier");
        await page.getByRole("dialog").getByLabel("Job title").fill("Shipping manager");
        await page.getByRole("dialog").getByLabel("Mobile").fill("207-555-0188");
        await shot(page, "contact-dialog", false);
        await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

        await page.getByRole("button", { name: "Add address" }).click();
        await page.getByRole("dialog").getByLabel("Street address").fill("1 Mill Street");
        await page.getByRole("dialog").getByLabel("Town").fill("Lincoln");
        await page.getByRole("dialog").getByLabel("ZIP").fill("04457");
        await shot(page, "address-dialog", false);
        await page.context().close();

        await stateShots(browser, viewport, theme, "/customers", "**/api/v1/customers?*", "customers", /couldn't load/i);
      });

      test("unit inventory", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/units");
        await expect(page.getByRole("list", { name: "Units" })).toBeVisible();
        await shot(page, "units-stock-grid");

        if (viewport !== "phone") {
          // Phones always get cards; the table view is for wider screens.
          await page.getByRole("button", { name: "Table" }).click();
          await expect(page.getByText("HHKHHN04P00123").filter({ visible: true }).first()).toBeVisible();
          await shot(page, "units-stock-table");
          await page.getByRole("button", { name: "Photo cards" }).click();
        }

        await page.goto("/units?scope=all");
        await expect(page.getByRole("list", { name: "Units" })).toBeVisible();
        await shot(page, "units-all");

        await page.goto("/units?scope=all&make=Hyundai&condition=used&fuel_type=diesel");
        await expect(page.getByRole("list", { name: "Units" })).toBeVisible();
        if (narrow) {
          await page.getByRole("button", { name: /^Filters/ }).click();
          await expect(page.getByRole("dialog", { name: "Filters" })).toBeVisible();
          await shot(page, "units-filters-open", false);
          await page.keyboard.press("Escape");
        } else {
          await shot(page, "units-filtered");
        }

        await page.goto("/units?q=no-such-forklift");
        await expect(page.getByText("No units match")).toBeVisible();
        await shot(page, "units-empty");
        await page.context().close();

        const service = await newPage(browser, viewport, theme, authFile("service"));
        await service.goto("/units");
        await expect(service.getByRole("list", { name: "Units" })).toBeVisible();
        await shot(service, "units-stock-grid-service-no-prices");
        await service.context().close();

        await stateShots(browser, viewport, theme, "/units", "**/api/v1/units?*", "units", /couldn't load/i);
      });

      test("unit detail", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        const stockUnit = await unitId(page, "HHKHHN04P00123");
        await page.goto(`/units/${stockUnit}`);
        await expect(page.getByText("Pricing (admin and sales only)")).toBeVisible();
        await shot(page, "unit-detail-admin");

        await page.getByRole("button", { name: "View larger" }).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await shot(page, "unit-photo-lightbox", false);
        await page.keyboard.press("Escape");

        await page.getByRole("button", { name: "Add hours" }).click();
        await page.getByRole("dialog").getByLabel("Hours").fill("1200");
        await shot(page, "hours-dialog", false);
        await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

        await page.getByRole("button", { name: "Change owner" }).first().click();
        await expect(page.getByRole("dialog", { name: "Change owner" })).toBeVisible();
        await shot(page, "change-owner-dialog", false);
        await page.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();

        const review = await unitId(page, "HHKHHN04L0094");
        await page.goto(`/units/${review}`);
        await expect(page.getByText("This record needs a second look.")).toBeVisible();
        await shot(page, "unit-detail-needs-review");
        await page.context().close();

        const service = await newPage(browser, viewport, theme, authFile("service"));
        await service.goto(`/units/${stockUnit}`);
        await expect(service.getByRole("button", { name: "Add hours" })).toBeVisible();
        await shot(service, "unit-detail-service-no-prices");
        await service.context().close();

        const missing = await newPage(browser, viewport, theme, authFile("admin"));
        await missing.goto("/units/00000000-0000-0000-0000-000000000000");
        await expect(missing.getByText("Unit not found")).toBeVisible();
        await shot(missing, "unit-not-found");
        await missing.context().close();
      });

      test("unit card form", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/units/new");
        await expect(page.getByRole("heading", { name: "Add a unit", level: 1 })).toBeVisible();
        await shot(page, "unit-form-blank");

        await page.getByRole("button", { name: "Add unit" }).click();
        await expect(page.getByText("Enter at least a serial number, model or stock number.")).toBeVisible();
        await shot(page, "unit-form-errors", false);

        await page.getByLabel("Make", { exact: true }).fill("Hyundai");
        await page.getByLabel("Model", { exact: true }).fill("35LN-9A");
        await page.getByRole("textbox", { name: "Serial number" }).fill("HHKHHN04-P00123");
        await expect(page.getByText("This serial is already on")).toBeVisible();
        await shot(page, "unit-form-duplicate-serial", false);
        await page.context().close();

        const edit = await newPage(browser, viewport, theme, authFile("sales"));
        const id = await unitId(edit, "FGA25-70988");
        await edit.goto(`/units/${id}/edit`);
        await expect(edit.getByRole("heading", { name: /^Edit /, level: 1 })).toBeVisible();
        await shot(edit, "unit-form-filled");
        await edit.context().close();
      });
    });
  }
}
