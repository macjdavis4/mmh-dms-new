/**
 * Phase 7 screenshots: units changing hands, at desktop, tablet and phone
 * widths in light and dark mode, plus empty, loading and error states.
 * Nothing is saved: dialogs are filled in and photographed, then cancelled.
 *
 *   SCREENSHOT_PHASE=7 npx playwright test --project=screenshots
 */
import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(7);

async function unitId(page: Page, serial: string): Promise<string> {
  const found = (await (await page.request.get(`/api/v1/units?scope=all&q=${serial}`)).json()) as { results: { id: string }[] };
  return found.results[0]?.id ?? "";
}

async function customerId(page: Page, name: string): Promise<string> {
  const found = (await (await page.request.get(`/api/v1/customers?q=${encodeURIComponent(name)}`)).json()) as { results: { id: string }[] };
  return found.results[0]?.id ?? "";
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("unit page: ownership history with each deal", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        // Sold new in 2017, traded back in, now in prep to sell again.
        await page.goto(`/units/${await unitId(page, "HHKHFR04E00412")}`);
        const timeline = page.getByRole("list", { name: "Owners, newest first" });
        await expect(timeline).toContainText("Sold for $24,800");
        await shot(page, "unit-traded-back-in");
        await page.locator("#ownership").scrollIntoViewIfNeeded();
        await shot(page, "unit-ownership-history", false);

        await page.getByRole("button", { name: /Correct the record for Kennebec Cold Storage/ }).click();
        await expect(page.getByRole("dialog").getByLabel("Invoice or reference #")).toHaveValue("INV-7731");
        await shot(page, "correct-deal-dialog", false);
        await page.context().close();
      });

      test("change owner: sale, coming back, validation", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        // New in stock: the dialog offers a sale.
        await page.goto(`/units/${await unitId(page, "HHKHHN04P00123")}`);
        await page.getByRole("button", { name: "Change owner" }).first().click();
        const dialog = page.getByRole("dialog");
        await shot(page, "change-owner-sale-empty", false);
        await dialog.getByRole("button", { name: "Record sale" }).click();
        await expect(dialog.getByText("Pick the customer who bought it.")).toBeVisible();
        await shot(page, "change-owner-sale-error", false);
        await dialog.getByLabel("Sold to").fill("Katahdin");
        await page.getByRole("option", { name: /Katahdin Lumber/ }).click();
        await dialog.getByLabel("Sale price (optional)").fill("33900");
        await dialog.getByLabel("Hour meter (optional)").fill("6");
        await dialog.getByLabel("Invoice or reference # (optional)").fill("INV-10511");
        await expect(dialog.getByRole("note", { name: "What will change" })).toContainText("$33,900");
        await shot(page, "change-owner-sale-filled", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        // Sold to a customer: the dialog offers taking it back.
        await page.goto(`/units/${await unitId(page, "HHKHHC52C00316")}`);
        await page.getByRole("button", { name: "Change owner" }).first().click();
        await dialog.getByLabel("Came back to our stock").check();
        await dialog.getByLabel("Why").selectOption("repossession");
        await dialog.getByLabel("What we paid (optional)").fill("6000");
        await expect(dialog.getByRole("note", { name: "What will change" })).toContainText("Cost becomes $6,000");
        await shot(page, "change-owner-coming-back", false);
        await page.context().close();
      });

      test("undo the latest change (admin)", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto(`/units/${await unitId(page, "FGC25-P05-11873")}`);
        await page.getByRole("button", { name: "Undo this change of hands" }).click();
        await expect(page.getByRole("alertdialog")).toBeVisible();
        await shot(page, "undo-change-confirm", false);
        await page.context().close();
      });

      test("bought and sold", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/units/changes");
        await expect(page.getByLabel("Totals for these filters")).toContainText("in sales");
        await expect(page.getByText("Repossession").first()).toBeVisible();
        await shot(page, "bought-and-sold");
        await page.getByRole("tab", { name: "Came back" }).click();
        await expect(page).toHaveURL(/direction=in/);
        await expect(page.getByText("Trade-in").first()).toBeVisible();
        await shot(page, "bought-and-sold-came-back");
        await page.context().close();

        const viewer = await newPage(browser, viewport, theme, authFile("viewer"));
        await viewer.goto("/units/changes");
        await expect(viewer.getByText("Repossession").first()).toBeVisible();
        await shot(viewer, "bought-and-sold-read-only");
        await viewer.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("sales"));
        await empty.route("**/api/v1/unit-changes?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.route("**/api/v1/unit-changes/totals*", (route) =>
          route.fulfill({ json: { sold: { count: 0, total: null, margin: null, with_margin: 0 }, came_back: { count: 0, total: null }, between_customers: { count: 0 } } }),
        );
        await empty.goto("/units/changes");
        await expect(empty.getByText("No units have changed hands yet")).toBeVisible();
        await shot(empty, "bought-and-sold-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("sales"));
        await slow.route("**/api/v1/unit-changes**", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/units/changes");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/bought-and-sold-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("sales"));
        await broken.route("**/api/v1/unit-changes**", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/units/changes");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "bought-and-sold-error");
        await broken.context().close();
      });

      test("customer: units they used to own", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto(`/customers/${await customerId(page, "Kennebec Cold Storage")}`);
        const former = page.locator("#former-units");
        await expect(former).toContainText("25L-7A");
        await former.scrollIntoViewIfNeeded();
        await shot(page, "customer-former-units", false);
        await page.context().close();
      });
    });
  }
}
