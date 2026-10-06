import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { authFile } from "./helpers";

/** A made-up supplier invoice with a fresh number, so each run is new. */
function sampleInvoice(ext: "pdf" | "png"): { file: string; number: string } {
  const backend = path.resolve(import.meta.dirname, "../../backend");
  const python = process.env.E2E_PYTHON ?? path.join(backend, ".venv/bin/python");
  const number = `E2E-${Date.now().toString().slice(-7)}`;
  const file = path.join(mkdtempSync(path.join(tmpdir(), "mmh-invoice-")), `invoice.${ext}`);
  execFileSync(python, ["manage.py", "make_sample_invoice", file, "--number", number], {
    cwd: backend,
    env: { ...process.env, DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE ?? "config.settings.e2e" },
  });
  return { file, number };
}

test.describe("as parts", () => {
  test.use({ storageState: authFile("parts") });

  test("upload an invoice, check it, receive part of it, and clear the backorder", async ({ page }) => {
    const sample = sampleInvoice("pdf");
    await page.goto("/parts/invoices");
    await page.getByTestId("invoice-file").setInputFiles(sample.file);

    // Read on the server: supplier, number and lines are suggested.
    await expect(page.getByRole("heading", { name: "Hyundai parts", level: 1 })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByLabel("Invoice #")).toHaveValue(sample.number);
    await expect(page.getByText("Matches the invoice total")).toBeVisible();
    const lines = page.getByRole("list", { name: "Invoice lines" });
    await expect(lines.getByRole("listitem")).toHaveCount(5);
    const unknown = lines.getByRole("listitem", { name: "Line 5" });
    await expect(unknown).toContainText("Part not in the catalog");

    // The seat belt isn't stocked here: mark it as not a stock item, then save.
    await unknown.getByLabel("Not a stock item").check();
    await page.getByRole("button", { name: "Save invoice" }).click();
    await expect(page.getByText("Invoice saved")).toBeVisible();

    // Two fuel filters were missing from the box.
    await page.getByRole("button", { name: "Receive into stock" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("31N4-01060 arrived")).toHaveValue("6");
    await dialog.getByLabel("31N4-01060 arrived").fill("4");
    await dialog.getByRole("button", { name: "Receive into stock" }).click();
    await expect(page.getByText("Received. The rest is waiting under Backorders.")).toBeVisible();
    await expect(page.locator("text=Partly received >> visible=true").first()).toBeVisible();
    const fuel = page.getByRole("list", { name: "Invoice lines" }).getByRole("listitem").filter({ hasText: "31N4-01060" });
    await expect(fuel).toContainText("4 of 8 in");
    await expect(fuel).toContainText("4 to come");

    // On the backorders list; two turn up, the supplier cancels the rest.
    await page.goto("/parts/invoices?tab=backorders");
    const row = page.getByRole("list", { name: "Backorders" }).getByRole("listitem").filter({ hasText: sample.number });
    await expect(row).toContainText("31N4-01060");
    await row.getByRole("button", { name: "Arrived" }).click();
    await dialog.getByLabel("How many arrived").fill("2");
    await dialog.getByRole("button", { name: "Receive into stock" }).click();
    await expect(page.getByText("2 of 31N4-01060 received")).toBeVisible();
    await row.getByRole("button", { name: "Won't come" }).click();
    await dialog.getByLabel("Why").fill("Supplier cancelled the backorder");
    await dialog.getByRole("button", { name: "Won't come" }).click();
    await expect(row).toHaveCount(0);

    await page.getByRole("tab", { name: "Received" }).click();
    await expect(page.locator(`text=${sample.number} >> visible=true`).first()).toBeVisible();
  });

  test("a phone photo of an invoice is read too", async ({ page }) => {
    const sample = sampleInvoice("png");
    await page.goto("/parts/invoices");
    await page.getByTestId("invoice-file").setInputFiles(sample.file);
    await expect(page.getByLabel("Invoice #")).toHaveValue(sample.number, { timeout: 60_000 });
    await expect(page.getByText("from the picture")).toBeVisible();
    await expect(page.getByRole("img", { name: /The uploaded invoice/ })).toBeVisible();
    // Not received after all: cancel it.
    await page.getByRole("button", { name: "Cancel" }).click();
    await page.getByRole("dialog").getByLabel("Why").fill("Testing the reader");
    await page.getByRole("dialog").getByRole("button", { name: "Cancel invoice" }).click();
    await expect(page.getByText("Cancelled:")).toBeVisible();
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("can't see invoices (they show our cost)", async ({ page }) => {
    await page.goto("/parts");
    await expect(page.getByRole("link", { name: "Invoices" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Parts invoices" })).toHaveCount(0);
    await page.goto("/parts/invoices");
    await expect(page).toHaveURL(/\/$/);
    expect((await page.request.get("/api/v1/parts-invoices")).status()).toBe(403);
  });
});
