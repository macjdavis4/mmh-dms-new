/**
 * Phase 6 screenshots: the print buttons at desktop, tablet and phone widths
 * in light and dark mode, plus the PDFs themselves (saved next to the
 * pictures; turn them into images with infra/scripts/pdf-to-png.sh).
 *
 *   SCREENSHOT_PHASE=6 npx playwright test --project=screenshots
 */
import { writeFile } from "node:fs/promises";

import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(6);

async function ids(page: Page) {
  const wo = (await (await page.request.get("/api/v1/work-orders?scope=all&q=Mast%20chatters")).json()) as { results: { id: string }[] };
  const unit = (await (await page.request.get("/api/v1/units?scope=all&q=FGA25-70988")).json()) as { results: { id: string }[] };
  const stock = (await (await page.request.get("/api/v1/units?scope=all&q=HHKHHN04P00123")).json()) as { results: { id: string }[] };
  return { wo: wo.results[0]?.id ?? "", unit: unit.results[0]?.id ?? "", stock: stock.results[0]?.id ?? "" };
}

test("sample PDFs", async ({ browser }) => {
  const page = await newPage(browser, "desktop", "light", authFile("sales"));
  const { wo, unit, stock } = await ids(page);
  for (const [name, url] of [
    ["work-order", `/api/v1/work-orders/${wo}/pdf`],
    ["spec-sheet", `/api/v1/units/${unit}/spec-sheet`],
    ["spec-sheet-with-price", `/api/v1/units/${stock}/spec-sheet?price=1`],
  ] as const) {
    const res = await page.request.get(url);
    expect(res.status()).toBe(200);
    await writeFile(`${OUT}/${name}.pdf`, await res.body());
  }
  await page.context().close();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("print buttons", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("service"));
        const { wo, unit } = await ids(page);
        await page.goto(`/service/${wo}`);
        await expect(page.getByRole("link", { name: "Print" })).toBeVisible();
        await shot(page, "work-order-print-button", false);
        await page.goto(`/units/${unit}`);
        await expect(page.getByRole("link", { name: "Spec sheet" })).toBeVisible();
        await shot(page, "unit-spec-sheet-button", false);
        await page.context().close();

        const sales = await newPage(browser, viewport, theme, authFile("sales"));
        await sales.goto(`/units/${unit}`);
        await sales.getByRole("button", { name: "Spec sheet" }).click();
        await expect(sales.getByRole("menuitem", { name: "Spec sheet with asking price" })).toBeVisible();
        await shot(sales, "unit-spec-sheet-menu", false);
        await sales.context().close();
      });
    });
  }
}
