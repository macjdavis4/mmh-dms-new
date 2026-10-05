/**
 * Phase 9 screenshots: the parts catalog, at desktop, tablet and phone
 * widths in light and dark mode, plus empty, loading and error states.
 * Nothing is saved: forms are filled in and photographed, then left.
 *
 *   SCREENSHOT_PHASE=9 npx playwright test --project=screenshots
 */
import { expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(9);

async function partId(page: Page, number: string): Promise<string> {
  const res = (await (await page.request.get(`/api/v1/parts?replaced=1&q=${number}`)).json()) as { results: { id: string; part_number: string }[] };
  return res.results.find((p) => p.part_number === number)?.id ?? "";
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("parts list", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/parts");
        await expect(page.locator("text=Engine oil filter >> visible=true").first()).toBeVisible();
        await shot(page, "parts-list");
        await page.getByRole("searchbox", { name: "Search" }).fill("p550084");
        await expect(page.locator("text=31N4-01050 >> visible=true").first()).toBeVisible();
        await shot(page, "parts-search-cross-reference");
        await page.context().close();

        const viewer = await newPage(browser, viewport, theme, authFile("service"));
        await viewer.goto("/parts?category=filters");
        await expect(viewer.locator("text=Engine oil filter >> visible=true").first()).toBeVisible();
        await shot(viewer, "parts-list-mechanic");
        await viewer.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("parts"));
        await empty.route("**/api/v1/parts?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.goto("/parts");
        await expect(empty.getByText("No parts in the catalog yet")).toBeVisible();
        await shot(empty, "parts-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("parts"));
        await slow.route("**/api/v1/parts?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/parts");
        await expect(slow.getByRole("status").getByText("Loading")).toBeAttached();
        await slow.screenshot({ path: `${OUT}/parts-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("parts"));
        await broken.route("**/api/v1/parts?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/parts");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "parts-error");
        await broken.context().close();
      });

      test("part pages", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto(`/parts/${await partId(page, "31N4-01050")}`);
        await expect(page.getByRole("list", { name: "Cross references" })).toBeVisible();
        await shot(page, "part-detail");
        await page.goto(`/parts/${await partId(page, "XKBH-00117")}`);
        await expect(page.getByRole("note")).toContainText("XKBH-00117A");
        await shot(page, "part-replaced");
        await page.goto(`/parts/${await partId(page, "31N4-01050")}/edit`);
        await expect(page.getByLabel("Part number", { exact: true })).toHaveValue("31N4-01050");
        await shot(page, "part-edit");
        await page.goto("/parts/new");
        await page.getByRole("button", { name: "Add part" }).click();
        await expect(page.getByText("Enter the part number.")).toBeVisible();
        await shot(page, "part-new-errors", false);
        await page.getByLabel("Part number", { exact: true }).fill("31N4 01050");
        await page.getByLabel("Maker").fill("Hyundai");
        await expect(page.getByRole("alert").filter({ hasText: "is already in the catalog" })).toBeVisible();
        await shot(page, "part-new-duplicate", false);
        await page.context().close();

        const viewer = await newPage(browser, viewport, theme, authFile("service"));
        await viewer.goto(`/parts/${await partId(viewer, "31N4-01050")}`);
        await expect(viewer.getByText("$18.50")).toBeVisible();
        await shot(viewer, "part-detail-mechanic");
        await viewer.context().close();
      });

      test("bins", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("parts"));
        await page.goto("/parts/bins");
        await expect(page.getByRole("list", { name: "Bins" })).toContainText("A-01-1");
        await shot(page, "bins");
        await page.getByRole("button", { name: "Add bin" }).click();
        await shot(page, "bin-dialog", false);
        await page.context().close();
      });
    });
  }
}
