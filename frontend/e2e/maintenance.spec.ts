import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("add a plan, see it due, make the work order, complete it", async ({ page }) => {
    const problems = watchConsole(page);
    const name = `Mast chain check ${Date.now()}`;
    await page.goto("/units?scope=customer");
    await page.getByRole("list", { name: "Units" }).getByRole("link", { name: /70D-9/ }).click();
    await page.getByRole("button", { name: "Add plan" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Annual safety inspection" }).click();
    await expect(dialog.getByLabel("Every … days")).toHaveValue("365");
    await dialog.getByLabel("Name").fill(name);
    await dialog.getByLabel("Every … days").fill("30");
    await dialog.getByLabel("Last done on").fill("2026-01-01");
    await dialog.getByRole("button", { name: "Add plan" }).click();

    const plans = page.getByRole("list", { name: "Maintenance plans" });
    const row = plans.getByRole("listitem").filter({ hasText: name });
    await expect(row.getByText("Overdue", { exact: true })).toBeVisible();
    await expect(row.getByText(/Overdue by \d+ days/)).toBeVisible();

    // It's on the due list too.
    await page.goto("/service/maintenance");
    await expect(page.getByRole("list", { name: "Maintenance due" }).getByText(name)).toBeVisible();

    await page.getByRole("list", { name: "Maintenance due" }).getByRole("listitem").filter({ hasText: name }).getByRole("button", { name: "Work order" }).click();
    await expect(page).toHaveURL(/\/service\/[0-9a-f-]{36}$/);
    await expect(page.getByText(`(${name})`)).toBeVisible();
    await page.getByLabel("Correction").fill("Checked and adjusted mast chains.");
    await page.getByRole("button", { name: "Complete" }).click();
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();

    await page.getByRole("link", { name: /Hyundai 70D-9/ }).click();
    await expect(page.getByRole("list", { name: "Maintenance plans" }).getByRole("listitem").filter({ hasText: name }).getByText("Up to date")).toBeVisible();
    expect(problems).toEqual([]);
  });
});

test.describe("as read-only", () => {
  test.use({ storageState: authFile("viewer") });

  test("sees what's due but can't act", async ({ page }) => {
    await page.goto("/service/maintenance");
    await expect(page.getByRole("heading", { name: "Maintenance due", level: 1 })).toBeVisible();
    await expect(page.getByRole("list", { name: "Maintenance due" }).getByText("Battery and charger check")).toBeVisible();
    await expect(page.getByRole("button", { name: "Work order" })).toHaveCount(0);
  });
});
