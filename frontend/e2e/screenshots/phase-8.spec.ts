/**
 * Phase 8 screenshots: quotes and sales, at desktop, tablet and phone widths
 * in light and dark mode, plus empty, loading and error states, and a sample
 * quote PDF (turn it into pictures with infra/scripts/pdf-to-png.sh).
 * Nothing is saved: dialogs are opened and photographed, then closed.
 *
 *   SCREENSHOT_PHASE=8 npx playwright test --project=screenshots
 */
import { writeFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(8);

async function quoteId(page: Page, customer: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/quotes?scope=all&q=${encodeURIComponent(customer)}`)).json()) as { results: { id: string }[] };
  return res.results[0]?.id ?? "";
}

async function unitId(page: Page, serial: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/units?scope=all&q=${serial}`)).json()) as { results: { id: string }[] };
  return res.results[0]?.id ?? "";
}

test("sample quote PDF", async ({ browser }) => {
  const page = await newPage(browser, "desktop", "light", authFile("sales"));
  const res = await page.request.get(`/api/v1/quotes/${await quoteId(page, "Downeast")}/pdf`);
  expect(res.status()).toBe(200);
  await writeFile(`${OUT}/quote.pdf`, await res.body());
  await page.context().close();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("sales list", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/sales");
        await expect(page.locator("text=Penobscot Paper Co. >> visible=true").first()).toBeVisible();
        await shot(page, "sales-open");
        await page.getByRole("tab", { name: "Sold" }).click();
        await expect(page.locator("text=Katahdin Lumber >> visible=true").first()).toBeVisible();
        await shot(page, "sales-sold");
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("sales"));
        await empty.route("**/api/v1/quotes?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.goto("/sales");
        await expect(empty.getByText("No open quotes")).toBeVisible();
        await shot(empty, "sales-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("sales"));
        await slow.route("**/api/v1/quotes?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/sales");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/sales-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("sales"));
        await broken.route("**/api/v1/quotes?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/sales");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "sales-error");
        await broken.context().close();
      });

      test("quotes", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto(`/sales/${await quoteId(page, "Penobscot")}`);
        await expect(page.getByRole("list", { name: "Quote items" })).toBeVisible();
        await shot(page, "quote-draft");
        await page.goto(`/sales/${await quoteId(page, "Downeast")}`);
        await expect(page.getByText("Machias Savings").or(page.getByLabel("Owed to").first())).toBeVisible();
        await shot(page, "quote-sent-trade-in");
        await page.goto(`/sales/${await quoteId(page, "Katahdin")}`);
        await expect(page.getByText(/Sold .* as S-/)).toBeVisible();
        await shot(page, "quote-sold");

        await page.goto(`/sales/${await quoteId(page, "Murphy")}`);
        await page.getByRole("button", { name: "Record sale" }).click();
        await expect(page.getByRole("note", { name: "What will happen" })).toBeVisible();
        await shot(page, "record-sale-dialog", false);
        await page.context().close();
      });

      test("new quote", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/sales/new");
        await expect(page.getByRole("heading", { name: "New quote" })).toBeVisible();
        await shot(page, "quote-new-empty");
        await page.getByRole("button", { name: "Create quote" }).click();
        await expect(page.getByText("Pick the customer.")).toBeVisible();
        await shot(page, "quote-new-error", false);
        await page.goto(`/sales/new?unit=${await unitId(page, "HHKHHL03P00052")}`);
        await expect(page.getByRole("list", { name: "Quote items" })).toContainText("30L-9A");
        await page.locator("#q-customer").fill("Bangor");
        await page.getByRole("option", { name: /Bangor Building Supply/ }).click();
        await page.getByRole("button", { name: "Add item" }).click();
        await page.getByLabel("Description").last().fill("LED blue safety light");
        await page.getByLabel("Price").last().fill("280");
        await page.getByRole("button", { name: "Add trade-in" }).click();
        await page.getByLabel("Model").last().fill("C25");
        await page.getByLabel("Make").last().fill("Clark");
        await page.getByLabel("Serial").last().fill("C232-0099");
        await page.getByLabel("Allowance").last().fill("1500");
        await page.evaluate(() => window.scrollTo(0, 0));
        await shot(page, "quote-new-filled");
        await page.context().close();
      });

      test("void sale and quote this unit (admin)", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto(`/sales/${await quoteId(page, "Katahdin")}`);
        await page.getByRole("button", { name: "Void sale" }).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await shot(page, "void-sale-dialog", false);
        await page.goto(`/units/${await unitId(page, "HHKHHL03P00052")}`);
        await expect(page.getByRole("link", { name: "Quote this unit" })).toBeVisible();
        await shot(page, "unit-quote-button", false);
        await page.context().close();
      });
    });
  }
}
