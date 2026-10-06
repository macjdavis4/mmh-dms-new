/**
 * Phase 11 screenshots: supplier invoices (list, backorders, checking,
 * receiving), at desktop, tablet and phone widths in light and dark mode,
 * plus empty, loading, reading and error states. Dialogs are filled in and
 * photographed, then cancelled; nothing is saved.
 *
 *   SCREENSHOT_PHASE=11 npx playwright test --project=screenshots
 */
import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(11);

async function invoiceId(page: Page, number: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/parts-invoices?status=all&q=${number}`)).json()) as { results: { id: string; invoice_number: string }[] };
  return res.results.find((i) => i.invoice_number === number)?.id ?? "";
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("invoice lists", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/parts/invoices");
        await expect(page.locator("text=HMA-558812 >> visible=true").first()).toBeVisible();
        await shot(page, "invoices");
        await page.getByRole("tab", { name: /Backorders/ }).click();
        await expect(page.getByRole("list", { name: "Backorders" })).toContainText("31N4-02100");
        await shot(page, "invoices-backorders");
        await page.getByRole("list", { name: "Backorders" }).getByRole("button", { name: "Won't come" }).first().click();
        await page.getByRole("dialog").getByLabel("Why").fill("Supplier cancelled the backorder");
        await shot(page, "backorder-wont-come-dialog", false);
        await page.getByRole("dialog").getByRole("button", { name: "Keep waiting" }).click();
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("parts"));
        await empty.route("**/api/v1/parts-invoices?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.route("**/api/v1/parts-invoices/backorders", (route) => route.fulfill({ json: [] }));
        await empty.goto("/parts/invoices");
        await expect(empty.getByText("Nothing to do")).toBeVisible();
        await shot(empty, "invoices-empty");
        await empty.goto("/parts/invoices?tab=backorders");
        await expect(empty.getByText("Nothing on backorder")).toBeVisible();
        await shot(empty, "invoices-backorders-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("parts"));
        await slow.route("**/api/v1/parts-invoices?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/parts/invoices");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/invoices-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("parts"));
        await broken.route("**/api/v1/parts-invoices?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/parts/invoices");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "invoices-error");
        await broken.context().close();
      });

      test("checking and receiving an invoice", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        const id = await invoiceId(page, "HMA-558812");
        await page.goto(`/parts/invoices/${id}`);
        await expect(page.getByRole("list", { name: "Invoice lines" }).getByRole("listitem")).toHaveCount(5);
        await expect(page.getByText("Matches the invoice total")).toBeVisible();
        await shot(page, "invoice-check");

        // A change makes the save bar appear.
        const line5 = page.getByRole("listitem", { name: "Line 5" });
        await line5.getByLabel("Not a stock item").check();
        await expect(page.getByRole("button", { name: "Save invoice" })).toBeVisible();
        await shot(page, "invoice-check-unsaved", false);
        await page.getByRole("button", { name: "Discard" }).click();

        await page.getByRole("button", { name: "Receive into stock" }).click();
        const dialog = page.getByRole("dialog");
        await dialog.getByLabel("31N4-01060 arrived").fill("4");
        await shot(page, "invoice-receive-dialog", false);
        await dialog.getByRole("button", { name: "Cancel" }).click();

        await page.getByRole("button", { name: "Cancel", exact: true }).click();
        await dialog.getByLabel("Why").fill("Entered twice");
        await shot(page, "invoice-cancel-dialog", false);
        await dialog.getByRole("button", { name: "Keep it" }).click();

        await page.getByText("What the reader saw").click();
        await expect(page.locator("pre")).toContainText("HMA-558812");
        await shot(page, "invoice-reader-text");

        await page.goto(`/parts/invoices/${await invoiceId(page, "HMA-558790")}`);
        await expect(page.getByText("2 to come")).toBeVisible();
        await shot(page, "invoice-partly-received");
        await page.context().close();

        const sales = await newPage(browser, viewport, theme, authFile("sales"));
        await sales.goto(`/parts/invoices/${await invoiceId(sales, "HMA-558812")}`);
        await expect(sales.getByLabel("Invoice #")).toHaveValue("HMA-558812");
        await shot(sales, "invoice-sales-view");
        await sales.context().close();

        const reading = await newPage(browser, viewport, theme, authFile("parts"));
        await reading.route(`**/api/v1/parts-invoices/${id}`, async (route) => {
          const real = (await (await route.fetch()).json()) as Record<string, unknown>;
          await route.fulfill({ json: { ...real, status: "reading", status_label: "Reading", original_name: "IMG_2041.jpg" } });
        });
        await reading.goto(`/parts/invoices/${id}`);
        await expect(reading.getByText("Reading the invoice…")).toBeVisible();
        await shot(reading, "invoice-reading");
        await reading.context().close();
      });
    });
  }
}
