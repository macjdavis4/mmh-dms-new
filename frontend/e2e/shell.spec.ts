import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.use({ storageState: authFile("service") });

test("theme toggle switches to dark and remembers it", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Change theme/ }).click();
  await page.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("global search explains what it will find", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("combobox")).toBeVisible();
  await page.keyboard.press("/");
  await expect(page.getByRole("combobox")).toBeFocused();
  await page.getByRole("combobox").fill("35LN-9A");
  await expect(page.getByText("No matches for “35LN-9A”.")).toBeVisible();
  await expect(page.getByText(/become searchable as those sections are added/)).toBeVisible();
});

test("sections that aren't built yet say when they arrive", async ({ page }) => {
  await page.goto("/units");
  await expect(page.getByRole("heading", { name: "Arrives in phase 2" })).toBeVisible();
});

test("unknown pages show a friendly 404", async ({ page }) => {
  await page.goto("/no-such-page");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("non-admins are sent away from admin pages", async ({ page }) => {
  await page.goto("/admin/users");
  await expect(page).toHaveURL(/\/$/);
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("menu opens as a drawer and search opens full width", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(page.getByRole("dialog").getByRole("navigation", { name: "Main" })).toBeVisible();
    await page.getByRole("dialog").getByRole("link", { name: "My account" }).click();
    await expect(page.getByRole("heading", { name: "My account", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("dialog").getByRole("searchbox")).toBeVisible();
    expect(problems).toEqual([]);
  });
});
