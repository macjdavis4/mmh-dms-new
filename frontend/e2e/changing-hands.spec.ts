import { type APIRequestContext, expect, test } from "@playwright/test";

import { authFile } from "./helpers";

const BASE = "http://localhost:8000";

async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get("/api/v1/auth/csrf");
  const cookie = (await request.storageState()).cookies.find((c) => c.name === "mmh_csrftoken");
  return { "X-CSRFToken": cookie?.value ?? "", Referer: BASE };
}

/** A fresh unit in our stock, so the test can sell it however often it runs. */
async function stockUnit(request: APIRequestContext): Promise<{ id: string; serial: string }> {
  const serial = `E2E-CH-${Date.now()}`;
  const res = await request.post("/api/v1/units", {
    headers: await csrfHeaders(request),
    data: {
      make: "Hyundai",
      model: "30L-7A",
      serial_number: serial,
      condition: "new",
      stock_status: "available",
      cost: "20500",
      asking_price: "27900",
      card_date: "2025-01-02",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return { id: ((await res.json()) as { id: string }).id, serial };
}

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("sell a unit, take it back as a trade-in, see both deals", async ({ page }) => {
    const unit = await stockUnit(page.request);
    await page.goto(`/units/${unit.id}`);

    // Sold to a customer.
    await page.getByRole("button", { name: "Change owner" }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Sold to a customer.")).toBeVisible();
    await expect(dialog.getByLabel("Why")).toHaveValue("sold");
    await dialog.getByRole("button", { name: "Record sale" }).click();
    await expect(dialog.getByText("Pick the customer who bought it.")).toBeVisible();
    await dialog.getByLabel("Sold to").fill("Katahdin");
    await page.getByRole("option", { name: /Katahdin Lumber/ }).click();
    await dialog.getByLabel("Sale price (optional)").fill("26500");
    await dialog.getByLabel("Hour meter (optional)").fill("15");
    await dialog.getByLabel("Invoice or reference # (optional)").fill("INV-E2E");
    const effects = dialog.getByRole("note", { name: "What will change" });
    await expect(effects).toContainText("Stock status becomes Sold.");
    await expect(effects).toContainText("$20,500");
    await dialog.getByRole("button", { name: "Record sale" }).click();
    await expect(page.getByText("Sale recorded")).toBeVisible();

    const timeline = page.getByRole("list", { name: "Owners, newest first" });
    await expect(timeline).toContainText("Sold for $26,500 · cost $20,500 · margin $6,000");
    await expect(timeline).toContainText("Ref INV-E2E · 15 h");
    await expect(page.getByText("Sold", { exact: true }).first()).toBeVisible();

    // Comes back as a trade-in.
    await page.getByRole("button", { name: "Change owner" }).first().click();
    await dialog.getByLabel("Came back to our stock").check();
    await expect(dialog.getByLabel("Why")).toHaveValue("trade_in");
    await dialog.getByLabel("What we paid (optional)").fill("9000");
    await expect(effects).toContainText("Condition becomes Used.");
    await dialog.getByRole("button", { name: "Take into stock" }).click();
    await expect(page.getByText("Back in our stock")).toBeVisible();
    await expect(page.getByText("In prep", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Used", { exact: true }).first()).toBeVisible();
    await expect(timeline).toContainText("We paid $9,000");
    await expect(timeline).toContainText("Sold for $26,500"); // the first sale keeps its numbers

    // Correct the first sale's reference.
    await page.getByRole("button", { name: /Correct the record for Katahdin Lumber/ }).click();
    await dialog.getByLabel("Invoice or reference #").fill("INV-E2E-2");
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(timeline).toContainText("Ref INV-E2E-2");

    // Both changes are on Bought and sold.
    await page.getByRole("link", { name: "Bought and sold" }).first().click();
    await page.getByRole("searchbox", { name: "Search" }).fill(unit.serial);
    await expect(page.getByRole("table", { name: "Units that changed hands" }).getByRole("row")).toHaveCount(3);
    await page.getByRole("tab", { name: "Came back" }).click();
    await expect(page).toHaveURL(/direction=in/);
    await expect(page.getByRole("table", { name: "Units that changed hands" }).getByRole("row")).toHaveCount(2);
  });
});

test.describe("as admin", () => {
  test.use({ storageState: authFile("admin") });

  test("undo the latest change of hands", async ({ page }) => {
    const unit = await stockUnit(page.request);
    await page.goto(`/units/${unit.id}`);
    await page.getByRole("button", { name: "Change owner" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Sold to").fill("Pat Murphy");
    await page.getByRole("option", { name: /Pat Murphy/ }).click();
    await dialog.getByRole("button", { name: "Record sale" }).click();
    await expect(page.getByText("Sale recorded")).toBeVisible();

    await page.getByRole("button", { name: "Undo this change of hands" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Undo change" }).click();
    await expect(page.getByText("Change undone")).toBeVisible();
    await expect(page.getByText("Available", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("list", { name: "Owners, newest first" }).getByRole("listitem")).toHaveCount(1);
  });
});

test.describe("as read only", () => {
  test.use({ storageState: authFile("viewer") });

  test("Bought and sold without any money", async ({ page }) => {
    await page.goto("/units/changes");
    await expect(page.getByRole("heading", { name: "Bought and sold" })).toBeVisible();
    await expect(page.getByRole("table", { name: "Units that changed hands" })).toContainText("Repossession");
    await expect(page.getByText(/\$\d/)).toHaveCount(0);
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("sees the history but can't change owners", async ({ page }) => {
    const found = (await (await page.request.get("/api/v1/units?scope=all&q=HHKHFR04E00412")).json()) as { results: { id: string }[] };
    await page.goto(`/units/${found.results[0]?.id}`);
    const timeline = page.getByRole("list", { name: "Owners, newest first" });
    await expect(timeline).toContainText("Trade-in");
    await expect(timeline).toContainText("Kennebec Cold Storage");
    await expect(timeline).not.toContainText("$");
    await expect(page.getByRole("button", { name: "Change owner" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Bought and sold" })).toHaveCount(0);
  });
});
