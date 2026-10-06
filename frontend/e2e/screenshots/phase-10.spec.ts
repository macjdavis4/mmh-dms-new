/**
 * Phase 10 screenshots: the parts stock ledger, low stock and parts on work
 * orders, at desktop, tablet and phone widths in light and dark mode, plus
 * empty, loading and error states. Dialogs are filled in and photographed,
 * then cancelled; nothing is saved except one stock check run by the admin.
 *
 *   SCREENSHOT_PHASE=10 npx playwright test --project=screenshots
 */
import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(10);

async function partId(page: Page, number: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/parts?replaced=1&q=${number}`)).json()) as { results: { id: string; part_number: string }[] };
  return res.results.find((p) => p.part_number === number)?.id ?? "";
}

async function workOrderId(page: Page, complaint: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/work-orders?scope=open&q=${encodeURIComponent(complaint)}`)).json()) as { results: { id: string }[] };
  return res.results[0]?.id ?? "";
}

test.beforeAll(async ({ browser }) => {
  // One stock check, so the low-stock page has a result to show.
  const page = await newPage(browser, "desktop", "light", authFile("admin"));
  await page.goto("/parts/low-stock");
  await page.getByRole("button", { name: "Check now" }).click();
  await expect(page.getByText("Counts add up.")).toBeVisible();
  await page.context().close();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("parts list with stock", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/parts");
        await expect(page.locator("text=Engine oil filter >> visible=true").first()).toBeVisible();
        await shot(page, "parts-list-stock");
        await page.goto("/parts?stock=low");
        await expect(page.locator("text=Brake shoe set >> visible=true").first()).toBeVisible();
        await shot(page, "parts-list-low-filter");
        await page.context().close();
      });

      test("low stock", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/parts/low-stock");
        await expect(page.getByText("Counts add up.")).toBeVisible();
        await expect(page.locator("text=LPG regulator repair kit >> visible=true").first()).toBeVisible();
        await shot(page, "low-stock");
        await page.context().close();

        const admin = await newPage(browser, viewport, theme, authFile("admin"));
        // What the page shows if the nightly check ever finds a count that doesn't add up.
        await admin.route("**/api/v1/parts/low-stock", async (route) => {
          const real = (await (await route.fetch()).json()) as { results: unknown[]; last_check: Record<string, unknown> };
          await route.fulfill({
            json: {
              ...real,
              last_check: {
                ...real.last_check,
                ok: false,
                drift: [{ part: "00000000-0000-0000-0000-000000000000", part_number: "31N4-02100", ledger: "7.00", stored: "8.00" }],
              },
            },
          });
        });
        await admin.goto("/parts/low-stock");
        await expect(admin.getByText("Some counts don't add up.")).toBeVisible();
        await shot(admin, "low-stock-drift-admin");
        await admin.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("parts"));
        await empty.route("**/api/v1/parts/low-stock", (route) => route.fulfill({ json: { results: [], last_check: null } }));
        await empty.goto("/parts/low-stock");
        await expect(empty.getByText("Nothing is low")).toBeVisible();
        await shot(empty, "low-stock-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("parts"));
        await slow.route("**/api/v1/parts/low-stock", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/parts/low-stock");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/low-stock-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("parts"));
        await broken.route("**/api/v1/parts/low-stock", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/parts/low-stock");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "low-stock-error");
        await broken.context().close();
      });

      test("part stock and history", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        const oil = await partId(page, "31N4-01050");
        await page.goto(`/parts/${oil}`);
        await expect(page.getByRole("list", { name: "Stock history" })).toContainText("Hyundai invoice 55120");
        await shot(page, "part-stock");

        const stock = page.locator("#stock");
        const dialog = page.getByRole("dialog");
        await stock.getByRole("button", { name: "Receive" }).click();
        await dialog.getByLabel("How many arrived").fill("12");
        await dialog.getByLabel("Invoice or packing slip # (optional)").fill("Hyundai invoice 55298");
        await shot(page, "part-receive-dialog", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        await stock.getByRole("button", { name: "Count" }).click();
        await dialog.getByLabel("On the shelf").fill("19");
        await dialog.getByLabel("Why it's different (optional)").fill("Yearly count");
        await expect(dialog.getByText("−1 from the record.")).toBeVisible();
        await shot(page, "part-count-dialog", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        await page.getByRole("list", { name: "Stock history" }).getByRole("button", { name: "Reverse received of 12" }).click();
        await dialog.getByLabel("Why (optional)").fill("Entered twice");
        await shot(page, "part-reverse-dialog", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        const brakes = await partId(page, "31N4-40020");
        await page.goto(`/parts/${brakes}`);
        await expect(page.locator("#stock").getByText("Low: time to reorder")).toBeVisible();
        await shot(page, "part-stock-low");
        const kit = await partId(page, "RK-CA100");
        await page.goto(`/parts/${kit}`);
        await expect(page.getByText("Nothing yet. Count the shelf")).toBeVisible();
        await shot(page, "part-stock-never-counted");
        await page.context().close();

        const viewer = await newPage(browser, viewport, theme, authFile("service"));
        await viewer.goto(`/parts/${await partId(viewer, "BL-634")}`);
        await expect(viewer.getByRole("list", { name: "Stock history" })).toContainText("WO-");
        await shot(viewer, "part-stock-mechanic");
        await viewer.context().close();
      });

      test("parts on a work order", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        const wo = await workOrderId(page, "Mast chatters");
        await page.goto(`/service/${wo}`);
        const used = page.getByRole("list", { name: "Parts used" });
        await expect(used).toContainText("BL-634");
        await shot(page, "work-order-parts");

        const section = page.locator("#parts-used");
        const dialog = page.getByRole("dialog");
        await section.getByRole("button", { name: "Add part" }).click();
        await dialog.getByRole("combobox").fill("filter");
        await expect(dialog.getByRole("option").first()).toContainText("on hand");
        await shot(page, "work-order-add-part-search", false);
        await dialog.getByRole("option", { name: /31N4-01060/ }).click();
        await dialog.getByLabel("How many").fill("5");
        await dialog.getByRole("button", { name: "Add part" }).click();
        await expect(dialog.getByText("Only 3 of 31N4-01060 on hand")).toBeVisible();
        await shot(page, "work-order-add-part-error", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        await used.getByRole("button", { name: "Return BL-634 to stock" }).click();
        await dialog.getByLabel("How many go back").fill("2");
        await shot(page, "work-order-return-dialog", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();
        await page.context().close();

        const fresh = await newPage(browser, viewport, theme, authFile("sales"));
        await fresh.goto(`/service/${await workOrderId(fresh, "Hydraulic leak")}`);
        await expect(fresh.getByRole("list", { name: "Parts used" })).toContainText("AW32-5G");
        await shot(fresh, "work-order-parts-sales-view");
        await fresh.context().close();
      });
    });
  }
}
