import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("add a customer with a contact and an address", async ({ page }) => {
    const problems = watchConsole(page);
    const name = `Millinocket Mill Supply ${Date.now()}`;
    await page.goto("/customers");
    await expect(page.getByRole("heading", { name: "Customers", level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Add customer" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(name);
    await dialog.getByLabel("Phone").fill("207-555-0199");
    await dialog.getByRole("button", { name: "Add customer" }).click();
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();

    await page.getByRole("button", { name: "Add contact" }).click();
    await page.getByRole("dialog").getByLabel("First name").fill("Dana");
    await page.getByRole("dialog").getByLabel("Last name").fill("Thibodeau");
    await page.getByRole("dialog").getByLabel("Mobile").fill("207-555-0123");
    await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Dana Thibodeau")).toBeVisible();

    await page.getByRole("button", { name: "Add address" }).click();
    await page.getByRole("dialog").getByLabel("Street address").fill("12 Penobscot Ave");
    await page.getByRole("dialog").getByLabel("Town").fill("Millinocket");
    await page.getByRole("dialog").getByLabel("ZIP").fill("04462");
    await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("12 Penobscot Ave")).toBeVisible();

    await page.goto("/customers");
    await page.getByRole("searchbox", { name: /Search customers/ }).fill("Millinocket Mill");
    await expect(page.getByRole("link", { name: new RegExp(name) }).first()).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("a duplicate account number is refused inline", async ({ page }) => {
    await page.goto("/customers");
    await page.getByRole("button", { name: "Add customer" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(`Duplicate Account ${Date.now()}`);
    await dialog.getByLabel("Account number (optional)").fill("ppc-1001");
    await dialog.getByRole("button", { name: "Add customer" }).click();
    await expect(dialog.getByText(/already/i)).toBeVisible();
  });
});

test.describe("as read-only", () => {
  test.use({ storageState: authFile("viewer") });

  test("can look but not change", async ({ page }) => {
    await page.goto("/customers");
    await page.getByRole("link", { name: /Katahdin Lumber/ }).first().click();
    await expect(page.getByRole("heading", { name: "Katahdin Lumber", level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add contact" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Edit/ })).toHaveCount(0);
  });
});
