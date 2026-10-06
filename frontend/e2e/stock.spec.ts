import { type APIRequestContext, expect, request as playwrightRequest, test } from "@playwright/test";

import { authFile } from "./helpers";

const BASE = "http://localhost:8000";

async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get("/api/v1/auth/csrf");
  const cookie = (await request.storageState()).cookies.find((c) => c.name === "mmh_csrftoken");
  return { "X-CSRFToken": cookie?.value ?? "", Referer: BASE };
}

async function post<T>(request: APIRequestContext, url: string, data: Record<string, unknown>): Promise<T> {
  const res = await request.post(url, { headers: await csrfHeaders(request), data });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as T;
}

/** A fresh part, so each run starts from an empty shelf. */
async function freshPart(request: APIRequestContext, tag: string): Promise<{ id: string; number: string }> {
  const number = `E2E-${tag}-${Date.now().toString().slice(-6)}`;
  const part = await post<{ id: string }>(request, "/api/v1/parts", {
    manufacturer: "Hyundai",
    part_number: number,
    description: "Hydraulic filter",
    list_price: "25",
    cost: "11",
    reorder_point: "3",
    reorder_quantity: "6",
  });
  return { id: part.id, number };
}

test.describe("as parts", () => {
  test.use({ storageState: authFile("parts") });

  test("count, receive, reverse a mistake, and see it on the low-stock list", async ({ page }) => {
    const part = await freshPart(page.request, "S");
    await page.goto(`/parts/${part.id}`);
    const stock = page.locator("#stock");
    await expect(stock.getByText("Out of stock")).toBeVisible();
    await expect(page.getByText("Nothing yet. Count the shelf")).toBeVisible();

    await stock.getByRole("button", { name: "Count" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("On the shelf").fill("5");
    await expect(dialog.getByText("+5 from the record.")).toBeVisible();
    await dialog.getByRole("button", { name: "Save count" }).click();
    await expect(page.getByText("Counted. Now 5 on hand.")).toBeVisible();

    await stock.getByRole("button", { name: "Receive" }).click();
    await dialog.getByLabel("How many arrived").fill("10");
    await expect(dialog.getByLabel("Our cost each")).toHaveValue("11.00");
    await dialog.getByLabel("Invoice or packing slip # (optional)").fill("INV 9001");
    await dialog.getByRole("button", { name: "Add to stock" }).click();
    await expect(page.getByText("Received 10. Now 15 on hand.")).toBeVisible();
    await expect(stock).toContainText("15");

    const history = page.getByRole("list", { name: "Stock history" });
    await expect(history.getByRole("listitem")).toHaveCount(2);
    await expect(history).toContainText("INV 9001");

    // Oops: that delivery was for another store. Reverse it.
    await history.getByRole("button", { name: "Reverse received of 10" }).click();
    await dialog.getByLabel("Why (optional)").fill("Wrong store");
    await dialog.getByRole("button", { name: "Reverse it" }).click();
    await expect(page.getByText("Reversed. Now 5 on hand.")).toBeVisible();
    await expect(history.getByRole("listitem")).toHaveCount(3);
    await expect(history.getByText("Reversed", { exact: true })).toBeVisible();
    await expect(history.getByRole("button", { name: "Reverse received of 10" })).toBeDisabled();

    // Count down to the reorder point: it shows up as low.
    await stock.getByRole("button", { name: "Count" }).click();
    await dialog.getByLabel("On the shelf").fill("3");
    await dialog.getByRole("button", { name: "Save count" }).click();
    await expect(stock.getByText("Low: time to reorder")).toBeVisible();

    await page.getByRole("link", { name: "Parts", exact: true }).first().click();
    await page.getByRole("link", { name: "Low stock" }).first().click();
    await expect(page.getByRole("heading", { name: "Low stock", level: 1 })).toBeVisible();
    await expect(page.locator(`text=${part.number} >> visible=true`).first()).toBeVisible();
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("adds parts to a work order and returns what wasn't used", async ({ page }) => {
    // Setup as an admin: a unit, a work order, and a part with 4 on the shelf.
    const admin = await playwrightRequest.newContext({ baseURL: BASE, storageState: authFile("admin") });
    const part = await freshPart(admin, "W");
    await post(admin, "/api/v1/stock-movements/count", { part: part.id, counted: "4" });
    const unit = await post<{ id: string }>(admin, "/api/v1/units", { make: "Hyundai", model: "35LN-9A", serial_number: `E2E-W-${Date.now()}` });
    const wo = await post<{ id: string; number: string }>(admin, "/api/v1/work-orders", { unit: unit.id, complaint: "Replace hydraulic filter" });
    await admin.dispose();

    await page.goto(`/service/${wo.id}`);
    const section = page.locator("#parts-used");
    await expect(section.getByText("Nothing taken from stock yet.")).toBeVisible();
    await section.getByRole("button", { name: "Add part" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox").fill(part.number);
    await expect(dialog.getByRole("option", { name: new RegExp(part.number) })).toContainText("4 on hand");
    await dialog.getByRole("option", { name: new RegExp(part.number) }).click();
    await dialog.getByLabel("How many").fill("5");
    await dialog.getByRole("button", { name: "Add part" }).click();
    await expect(dialog.getByText(`Only 4 of ${part.number} on hand`)).toBeVisible();
    await dialog.getByLabel("How many").fill("2");
    await dialog.getByRole("button", { name: "Add part" }).click();
    await expect(page.getByText(`${part.number} added. 2 left on the shelf.`)).toBeVisible();

    const used = page.getByRole("list", { name: "Parts used" });
    await expect(used).toContainText("× 2");
    await expect(used).toContainText("$50.00");

    await used.getByRole("button", { name: `Return ${part.number} to stock` }).click();
    await dialog.getByLabel("How many go back").fill("1");
    await dialog.getByRole("button", { name: "Return to stock" }).click();
    await expect(page.getByText("1 back on the shelf.")).toBeVisible();
    await expect(used).toContainText("× 1");
    await expect(used).toContainText("$25.00");

    // The part's history shows the job.
    await used.getByRole("link", { name: part.number }).click();
    await expect(page.getByRole("list", { name: "Stock history" })).toContainText(wo.number);
    // Mechanics can't receive or count.
    await expect(page.locator("#stock").getByRole("button", { name: "Receive" })).toHaveCount(0);
  });
});
