import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.describe("as a mechanic", () => {
  test.use({ storageState: authFile("service") });

  test("search help for a task and land on the right heading", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto("/help");
    await expect(page.getByRole("heading", { name: "Help", level: 1 })).toBeVisible();
    // Browsing: sections for this role, no admin or sales-only articles.
    await expect(page.getByRole("heading", { name: "Service", level: 2 })).toBeVisible();
    await expect(page.getByRole("link", { name: /Users and roles/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^Quotes/ })).toHaveCount(0);

    await page.getByRole("searchbox", { name: "Search help" }).fill("remove a labor line");
    const results = page.getByRole("list", { name: "Search results" });
    await expect(results.getByRole("link").first()).toContainText("Work orders");
    await expect(page).toHaveURL(/\/help\?q=remove/);
    await results.getByRole("link").first().click();
    await expect(page).toHaveURL(/\/help\/work-orders#/);
    await expect(page.getByRole("heading", { name: "Work orders", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Remove a labor line" })).toBeInViewport();
    expect(errors).toEqual([]);
  });

  test("a typo still finds the article; nonsense explains what to try", async ({ page }) => {
    await page.goto("/help?q=maintanence");
    await expect(page.getByRole("list", { name: "Search results" }).getByRole("link").first()).toContainText("Planned maintenance");
    await page.getByRole("searchbox", { name: "Search help" }).fill("zzqx wobblefrump");
    await expect(page.getByText("Nothing found for “zzqx wobblefrump”")).toBeVisible();
  });

  test("the ? button opens help for the page you're on", async ({ page }) => {
    await page.goto("/service/maintenance");
    await page.getByRole("link", { name: /Help for this page: Planned maintenance/ }).click();
    await expect(page.getByRole("heading", { name: "Planned maintenance", level: 1 })).toBeVisible();
    // Links inside an article go to other articles and to app pages.
    await page.getByRole("link", { name: "Hour meter readings" }).click();
    await expect(page.getByRole("heading", { name: "Hour meter readings", level: 1 })).toBeVisible();
  });

  test("the global search shows help topics", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("combobox").fill("maintenance due");
    const results = page.locator(`[id="${await page.getByRole("combobox").getAttribute("aria-controls")}"]`);
    await expect(results.getByText("Help", { exact: true })).toBeVisible();
    await results.getByRole("link", { name: /Planned maintenance/ }).click();
    await expect(page).toHaveURL(/\/help\/maintenance/);
  });

  test("sales-only parts of an article are left out, and sales-only articles 404", async ({ page }) => {
    await page.goto("/help/unit-page");
    await expect(page.getByRole("heading", { name: "Stock status" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Prices" })).toHaveCount(0);
    await page.goto("/help/quotes");
    await expect(page.getByText("Help article not found")).toBeVisible();
  });
});

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("sees the price sections and sales articles", async ({ page }) => {
    await page.goto("/help/unit-page");
    await expect(page.getByRole("heading", { name: "Prices" })).toBeVisible();
    await page.goto("/help?q=trade-in");
    await expect(page.getByRole("list", { name: "Search results" })).toContainText("Quotes");
  });
});

test.describe("phone", () => {
  test.use({ storageState: authFile("parts"), viewport: { width: 390, height: 844 } });

  test("Help is in the menu and the ? button works", async ({ page }) => {
    await page.goto("/parts");
    await page.getByRole("link", { name: /Help for this page: Find a part/ }).click();
    await expect(page.getByRole("heading", { name: "Find a part", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Open menu" }).click();
    await page.getByRole("dialog").getByRole("link", { name: "Help" }).click();
    await expect(page.getByRole("heading", { name: "Help", level: 1 })).toBeVisible();
  });
});
