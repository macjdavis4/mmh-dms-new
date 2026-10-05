import { expect, test } from "@playwright/test";

import { authFile } from "./helpers";

test.describe("as parts", () => {
  test.use({ storageState: authFile("parts") });

  test("add a part with a bin and another brand's number, then find it by that number", async ({ page }) => {
    const n = Date.now().toString().slice(-6);
    const number = `E2E-${n}`;
    const crossRef = `XR-${n}-B`;
    await page.goto("/parts");
    await page.getByRole("link", { name: "Add part" }).click();
    await page.getByRole("button", { name: "Add part" }).click();
    await expect(page.getByText("Enter the part number.")).toBeVisible();
    await expect(page.getByText("Say what it is.")).toBeVisible();

    // The duplicate warning ignores dashes and case.
    await page.getByLabel("Part number", { exact: true }).fill("31n4 01050");
    await page.getByLabel("Maker").fill("Hyundai");
    await expect(page.getByRole("alert").filter({ hasText: "is already in the catalog" })).toBeVisible();

    await page.getByLabel("Part number", { exact: true }).fill(number);
    await page.getByLabel("Maker").fill("Hyundai");
    await page.getByLabel("Description").fill("Seat switch");
    await page.getByLabel("Category").selectOption("electrical");
    await page.getByLabel("Bin", { exact: true }).selectOption({ label: "C-01-3 · Electrical: switches and relays" });
    await page.getByLabel("Reorder at").fill("2");
    await page.getByLabel("Order this many").fill("4");
    await page.getByLabel("List price").fill("42");
    await page.getByLabel("Our cost").fill("19.5");
    await page.getByRole("button", { name: "Add a number" }).click();
    const refs = page.getByRole("list", { name: "Cross references" });
    await refs.getByLabel("Brand").fill("Generic");
    await refs.getByLabel("Their number").fill(crossRef);
    await page.getByRole("button", { name: "Add part" }).click();

    await expect(page.getByRole("heading", { name: number, level: 1 })).toBeVisible();
    await expect(page.getByText("C-01-3")).toBeVisible();
    await expect(page.getByText("$19.50")).toBeVisible();
    await expect(page.getByRole("list", { name: "Cross references" })).toContainText(crossRef);

    // Global search finds it by the other brand's number, typed without dashes.
    await page.getByRole("combobox", { name: /Search customers/ }).fill(crossRef.replaceAll("-", "").toLowerCase());
    await page.getByRole("link", { name: new RegExp(number) }).click();
    await expect(page.getByRole("heading", { name: number, level: 1 })).toBeVisible();

    // Replace it with a newer part.
    await page.getByRole("link", { name: "Edit part" }).click();
    await page.locator("#p-superseded").fill("31N4-40020");
    await page.getByRole("option", { name: /31N4-40020/ }).click();
    await page.getByRole("button", { name: "Save part" }).click();
    await expect(page.getByRole("note").filter({ hasText: "Replaced by" })).toContainText("31N4-40020");

    // Replaced parts drop out of the list unless asked for.
    await page.goto(`/parts?q=${number}`);
    await expect(page.getByText("No parts match")).toBeVisible();
    await page.getByLabel("Show replaced parts").check();
    await expect(page.getByRole("table", { name: "Parts" })).toContainText(number);
  });

  test("bins", async ({ page }) => {
    const code = `T-${Date.now().toString().slice(-5)}`;
    await page.goto("/parts/bins");
    await page.getByRole("button", { name: "Add bin" }).click();
    await page.getByRole("dialog").getByLabel("Code").fill(code.toLowerCase());
    await page.getByRole("dialog").getByRole("button", { name: "Save bin" }).click();
    await expect(page.getByRole("list", { name: "Bins" })).toContainText(code);
    await page.getByRole("button", { name: `Remove bin ${code}` }).click();
    await expect(page.getByText(`Bin ${code} removed`)).toBeVisible();
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("looks parts up but can't change them or see our cost", async ({ page }) => {
    await page.goto("/parts?q=oil%20filter");
    await page.getByRole("table", { name: "Parts" }).getByRole("link", { name: "31N4-01050" }).click();
    await expect(page.getByRole("list", { name: "Cross references" })).toContainText("P55-0084");
    await expect(page.getByText("$18.50")).toBeVisible();
    await expect(page.getByText("Our cost")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Edit part" })).toHaveCount(0);
    await page.goto("/parts");
    await expect(page.getByRole("link", { name: "Add part" })).toHaveCount(0);
  });
});
