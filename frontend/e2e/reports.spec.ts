import { expect, test } from "@playwright/test";

import { authFile } from "./helpers";

test.describe("as admin", () => {
  test.use({ storageState: authFile("admin") });

  test("dashboard tiles lead to reports; a report downloads as CSV", async ({ page }) => {
    await page.goto("/");
    const tiles = page.getByRole("region", { name: "At a glance" });
    await expect(tiles.getByText("Invoices to check")).toBeVisible();
    await expect(tiles.getByText("Units sold this month")).toBeVisible();
    await tiles.getByRole("link", { name: /Parts on the shelf/ }).click();

    await expect(page.getByRole("heading", { name: "Parts valuation", level: 1 })).toBeVisible();
    const table = page.getByRole("table", { name: "Parts valuation" });
    await expect(table).toContainText("31N4-01050");
    await expect(table.locator("tfoot")).toContainText("parts");
    await expect(page.getByText(/By category:/)).toBeVisible();

    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download CSV" }).click();
    expect((await download).suggestedFilename()).toMatch(/^parts-valuation-\d{4}-\d{2}-\d{2}\.csv$/);

    // Pick dates on a dated report.
    await page.getByRole("link", { name: "Reports", exact: true }).first().click();
    await page.getByRole("link", { name: /Units sold/ }).click();
    await page.getByLabel("Dates").selectOption("custom");
    await page.getByLabel("From", { exact: true }).fill("2026-03-01");
    await page.getByLabel("To", { exact: true }).fill("2026-03-31");
    await expect(page.getByText("Mar 1, 2026 to Mar 31, 2026")).toBeVisible();
    await expect(page.getByRole("table", { name: "Units sold" })).toContainText("Bangor Building Supply");
    await expect(page).toHaveURL(/from=2026-03-01/);

    // A row opens the unit.
    await page.getByRole("table", { name: "Units sold" }).getByRole("link").first().click();
    await expect(page).toHaveURL(/\/units\//);
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("sees service numbers and reports, not money ones", async ({ page }) => {
    await page.goto("/");
    const tiles = page.getByRole("region", { name: "At a glance" });
    await expect(tiles.getByText("Assigned to me")).toBeVisible();
    await expect(tiles.getByText("Parts on the shelf (at cost)")).toHaveCount(0);
    await expect(tiles.getByText("Units sold this month")).toHaveCount(0);
    await tiles.getByRole("link", { name: /Assigned to me/ }).click();
    await expect(page).toHaveURL(/\/service\?mine=1/);

    await page.goto("/reports");
    await expect(page.getByRole("link", { name: /Labor by mechanic/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Parts valuation/ })).toHaveCount(0);
    await page.getByRole("link", { name: /Parts used on work orders/ }).click();
    await expect(page.getByRole("columnheader", { name: "At list price" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Our cost" })).toHaveCount(0);

    await page.goto("/reports/parts-valuation");
    await expect(page.getByText("This report isn't available to you")).toBeVisible();
  });
});
