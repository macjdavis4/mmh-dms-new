import { expect, type Page, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

// A real 2x2 PNG (the server checks contents, not names).
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP438AARAwQCgAt7gX9iz9uhAAAAABJRU5ErkJggg==",
  "base64",
);

function csv(rows: Record<string, string>[]): Buffer {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const quote = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const lines = [columns.join(","), ...rows.map((r) => columns.map((c) => quote(r[c] ?? "")).join(","))];
  return Buffer.from(lines.join("\r\n") + "\r\n");
}

function cards(tag: string) {
  return [
    {
      customer_name: "Katahdin Lumber",
      card_date: "3/12/2024",
      mechanic: "Sam W.",
      unit_make: "Doosan",
      unit_model: "G25N-7",
      unit_serial: `E2E-${tag}-A`,
      hour_meter: "10288",
      engine_make: "Nissan",
      engine_model: "K25",
      forks: "1.75 x 4 x 48 STD; 1.75 x 4 x 48 STD",
      source_image_filename: `card-${tag}.png`,
    },
    {
      customer_name: "",
      owner: "stock",
      stock_status: "available",
      unit_make: "Hyundai",
      unit_model: "35LN-9A",
      unit_serial: `E2E-${tag}-B`,
      capacity_lbs: "3.5 ton",
    },
  ];
}

async function uploadCsv(page: Page, name: string, data: Buffer, scans: { name: string; buffer: Buffer }[] = []) {
  await page.goto("/imports/new");
  await page.locator('input[type="file"][accept=".csv,text/csv"]').setInputFiles({ name, mimeType: "text/csv", buffer: data });
  if (scans.length) {
    await page
      .locator('input[type="file"][multiple]')
      .setInputFiles(scans.map((s) => ({ name: s.name, mimeType: "image/png", buffer: s.buffer })));
  }
  await page.getByRole("button", { name: "Check file" }).click();
  await expect(page).toHaveURL(/\/imports\/[0-9a-f-]{36}$/);
}

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("template downloads and the list explains the steps", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/imports");
    await expect(page.getByRole("heading", { name: "Imports", level: 1 })).toBeVisible();
    await expect(page.getByText("How it works")).toBeVisible();
    const template = await page.request.get("/api/v1/imports/batches/template.csv");
    expect(template.ok()).toBeTruthy();
    expect((await template.text()).replace(/^﻿/, "").startsWith("customer_name,card_date,mechanic")).toBeTruthy();
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Download template" }).click()]);
    expect(download.suggestedFilename()).toBe("unit-import-template.csv");
    expect(problems).toEqual([]);
  });

  test("check, import, re-import and undo a file of cards", async ({ page }) => {
    const problems = watchConsole(page);
    const tag = Date.now().toString(36);
    await uploadCsv(page, `cards-${tag}.csv`, csv(cards(tag)), [{ name: `card-${tag}.png`, buffer: PNG }]);

    await expect(page.getByText("Ready to import", { exact: true }).first()).toBeVisible();
    const rows = page.getByRole("list", { name: "Import rows" });
    await expect(rows.getByText(`E2E-${tag}-A`)).toBeVisible();
    await expect(rows.getByText(/Kept “3.5 ton” in the notes/)).toBeVisible();
    await expect(rows.getByText(`card scan card-${tag}.png`)).toBeVisible();

    await page.getByRole("button", { name: "Import 2 units" }).click();
    await expect(page.getByText("Imported", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Units that need review" })).toBeVisible();

    // The imported unit has its card data, hours and scan.
    await rows.getByRole("link", { name: /Open unit/ }).first().click();
    await expect(page.getByRole("heading", { name: "Doosan G25N-7", level: 1 })).toBeVisible();
    await expect(page.getByText("Katahdin Lumber").first()).toBeVisible();
    await expect(page.getByText("10,288").first()).toBeVisible();
    await expect(page.getByText(`card-${tag}.png`).or(page.getByText("Original unit card")).first()).toBeVisible();

    // The same file again changes nothing.
    await uploadCsv(page, `cards-${tag}-again.csv`, csv(cards(tag)));
    await expect(page.getByRole("button", { name: "Nothing to import" })).toBeDisabled();
    await page.getByRole("button", { name: "Discard" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Discard" }).click();
    await expect(page.getByText("Discarded", { exact: true }).first()).toBeVisible();

    // Undo the first import.
    await page.goto("/imports");
    await page.getByRole("link", { name: `cards-${tag}.csv` }).first().click();
    await page.getByRole("button", { name: "Undo this import" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Undo import" }).click();
    await expect(page.getByText("Undone", { exact: true }).first()).toBeVisible();
    await page.goto(`/units?scope=all&q=E2E-${tag}`);
    await expect(page.getByText("No units match")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("rows with errors block the import until skipped", async ({ page }) => {
    const tag = Date.now().toString(36);
    await uploadCsv(page, `errors-${tag}.csv`, csv([{ unit_serial: `E2E-${tag}-C`, unit_make: "Hyundai" }, { unit_model: "No serial" }]));
    await page.getByRole("tab", { name: "Errors" }).click();
    await expect(page.getByText("Needs a unit serial (or a stock number).")).toBeVisible();
    const importButton = page.getByRole("button", { name: "Import 1 unit" });
    await expect(importButton).toBeDisabled();
    await page.getByLabel(/Skip the 1 rows with errors/).check();
    await importButton.click();
    await expect(page.getByText("Imported", { exact: true }).first()).toBeVisible();
  });

  test("an Excel workbook is explained, not uploaded", async ({ page }) => {
    await page.goto("/imports/new");
    await page
      .locator('input[type="file"][accept=".csv,text/csv"]')
      .setInputFiles({ name: "cards.xlsx", mimeType: "application/vnd.ms-excel", buffer: Buffer.from("PK") });
    await expect(page.getByRole("alert")).toContainText("CSV UTF-8");
    await expect(page.getByRole("button", { name: "Check file" })).toBeDisabled();
  });
});

test.describe("as parts", () => {
  test.use({ storageState: authFile("parts") });

  test("imports are not available", async ({ page }) => {
    await page.goto("/imports");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Imports" })).toHaveCount(0);
  });
});

test.describe("as admin", () => {
  test.use({ storageState: authFile("admin") });

  test("create an API key, see it once, revoke it", async ({ page }) => {
    const name = `Scanner ${Date.now()}`;
    await page.goto("/admin/api-keys");
    await page.getByRole("button", { name: "New key" }).click();
    await page.getByRole("dialog").getByLabel("Name").fill(name);
    await page.getByRole("dialog").getByRole("button", { name: "Create key" }).click();
    const key = await page.getByTestId("new-api-key").textContent();
    expect(key).toMatch(/^mmh_/);

    const res = await page.request.post("/api/v1/import/v1/units", {
      headers: { Authorization: `Api-Key ${key}` },
      data: { units: [{ unit_serial: "E2E-API-DRY" }], dry_run: true },
    });
    expect(res.status()).toBe(200);

    await page.getByRole("dialog").getByRole("button", { name: "Done" }).click();
    const row = page.getByRole("row", { name: new RegExp(name) });
    await row.getByRole("button", { name: "Revoke" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Revoke key" }).click();
    await expect(row.getByText("Revoked")).toBeVisible();
    const after = await page.request.post("/api/v1/import/v1/units", {
      headers: { Authorization: `Api-Key ${key}` },
      data: { units: [{ unit_serial: "E2E-API-DRY" }], dry_run: true },
    });
    expect(after.status()).toBe(401);
  });
});
