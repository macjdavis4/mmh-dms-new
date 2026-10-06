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
  const serial = `E2E-Q-${Date.now()}`;
  const res = await request.post("/api/v1/units", {
    headers: await csrfHeaders(request),
    data: { make: "Hyundai", model: "25L-9A", serial_number: serial, condition: "new", stock_status: "available", cost: "21000", asking_price: "28900", card_date: "2025-01-02" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return { id: ((await res.json()) as { id: string }).id, serial };
}

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("quote a unit with a trade-in, print it, and record the sale", async ({ page }) => {
    const unit = await stockUnit(page.request);
    const tradeSerial = `E2E-T-${Date.now()}`;
    await page.goto(`/units/${unit.id}`);
    await page.getByRole("link", { name: "Quote this unit" }).click();

    await expect(page.getByRole("heading", { name: "New quote" })).toBeVisible();
    const items = page.getByRole("list", { name: "Quote items" });
    await expect(items).toContainText("25L-9A");
    await expect(items.getByLabel("Price").first()).toHaveValue("28900");

    // Customer is required.
    await page.getByRole("button", { name: "Create quote" }).click();
    await expect(page.getByText("Pick the customer.")).toBeVisible();
    await page.locator("#q-customer").fill("Kennebec");
    await page.getByRole("option", { name: /Kennebec Cold Storage/ }).click();

    await page.getByRole("button", { name: "Add item" }).click();
    await items.getByLabel("Description").last().fill("Side shifter");
    await items.getByLabel("Price").last().fill("2400");
    await page.getByRole("button", { name: "Add discount" }).click();
    await items.getByLabel("Description").last().fill("Show special");
    await items.getByLabel("Amount off").fill("300");

    await page.getByRole("button", { name: "Add trade-in" }).click();
    const trades = page.getByRole("list", { name: "Trade-ins" });
    await trades.getByLabel("Make").fill("Clark");
    await trades.getByLabel("Model").fill("C25");
    await trades.getByLabel("Serial").fill(tradeSerial);
    await trades.getByLabel("Allowance").fill("1500");

    // 28900 + 2400 - 300 = 31000; tax 5.5% of (31000 - 1500) = 1622.50
    const totals = page.getByRole("region", { name: "Totals" });
    await expect(totals).toContainText("$31,000.00");
    await expect(totals).toContainText("$1,622.50");
    await expect(totals).toContainText("$31,122.50");

    await page.getByRole("button", { name: "Create quote" }).click();
    await expect(page.getByRole("heading", { name: /Quote Q-\d+/ })).toBeVisible();
    await expect(page).toHaveURL(/\/sales\/[0-9a-f-]{36}$/);

    // The PDF opens in a new tab.
    const print = page.getByRole("link", { name: "Print" });
    await expect(print).toHaveAttribute("target", "_blank");
    const pdf = await page.request.get((await print.getAttribute("href")) ?? "");
    expect(pdf.headers()["content-type"]).toBe("application/pdf");

    await page.getByRole("button", { name: "Mark sent" }).click();
    await expect(page.getByText("Sent", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Record sale" }).click();
    const dialog = page.getByRole("dialog");
    const happens = dialog.getByRole("note", { name: "What will happen" });
    await expect(happens).toContainText("Kennebec Cold Storage");
    await expect(happens).toContainText("(added to our units)");
    await dialog.getByLabel("Invoice # (optional)").fill("INV-E2E");
    await dialog.getByRole("button", { name: "Record sale" }).click();
    await expect(page.getByText(/Sold .* as S-\d+/)).toBeVisible();
    await expect(page.getByText("Invoice INV-E2E")).toBeVisible();
    await expect(page.getByRole("button", { name: "Record sale" })).toHaveCount(0);

    // The unit is sold to the customer; the trade-in is now in our stock.
    await page.goto(`/units/${unit.id}`);
    await expect(page.getByText("Sold", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("list", { name: "Owners, newest first" })).toContainText("Kennebec Cold Storage");
    const traded = (await (await page.request.get(`/api/v1/units?scope=stock&q=${tradeSerial}`)).json()) as { results: { stock_status: string }[] };
    expect(traded.results[0]?.stock_status).toBe("in_prep");
  });
});

test.describe("as admin", () => {
  test.use({ storageState: authFile("admin") });

  test("void a sale", async ({ page }) => {
    const unit = await stockUnit(page.request);
    const headers = await csrfHeaders(page.request);
    const customers = (await (await page.request.get("/api/v1/customers?q=Pat%20Murphy")).json()) as { results: { id: string }[] };
    const created = await page.request.post("/api/v1/quotes", {
      headers,
      data: { customer: customers.results[0]?.id, lines: [{ kind: "unit", unit: unit.id, unit_price: "27000" }] },
    });
    const quote = (await created.json()) as { id: string };
    await page.request.post(`/api/v1/quotes/${quote.id}/sell`, { headers, data: { sale_date: new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" }) } });

    await page.goto(`/sales/${quote.id}`);
    await page.getByRole("button", { name: "Void sale" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Void sale" })).toBeDisabled();
    await dialog.getByLabel("Why").fill("Financing fell through");
    await dialog.getByRole("button", { name: "Void sale" }).click();
    await expect(page.getByText(/was voided: Financing fell through/)).toBeVisible();
    await expect(page.getByText("Accepted", { exact: true })).toBeVisible();
    const back = (await (await page.request.get(`/api/v1/units/${unit.id}`)).json()) as { stock_status: string };
    expect(back.stock_status).toBe("available");
  });
});

for (const role of ["service", "viewer"] as const) {
  test.describe(`as ${role}`, () => {
    test.use({ storageState: authFile(role) });

    test("no sales, no quote buttons", async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Sales" })).toHaveCount(0);
      await page.goto("/sales");
      await expect(page).toHaveURL(/\/$/);
      expect((await page.request.get("/api/v1/quotes")).status()).toBe(403);
    });
  });
}
