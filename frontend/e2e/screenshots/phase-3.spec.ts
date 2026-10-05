/**
 * Phase 3 screenshots: batch import and API keys, at desktop, tablet and
 * phone widths in light and dark mode, plus empty, loading and error states.
 *
 *   SCREENSHOT_PHASE=3 npx playwright test --project=screenshots
 */
import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

import { authFile } from "../helpers";
import { newPage, outDir, shooter, THEMES, type Viewport, VIEWPORTS } from "./shots";

const OUT = outDir(3);
const BASE = "http://localhost:8000";

interface Batch {
  id: string;
}

async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get("/api/v1/auth/csrf");
  const cookie = (await request.storageState()).cookies.find((c) => c.name === "mmh_csrftoken");
  return { "X-CSRFToken": cookie?.value ?? "", Referer: BASE };
}

function csv(rows: Record<string, string>[]): Buffer {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const quote = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return Buffer.from([columns.join(","), ...rows.map((r) => columns.map((c) => quote(r[c] ?? "")).join(","))].join("\r\n") + "\r\n");
}

/** Realistic cards; `tag` keeps serials unique between runs. */
function cards(tag: string, n: number): Record<string, string>[] {
  const makes = [
    ["Hyundai", "30L-9A", "lpg", "6000"],
    ["Hyundai", "25D-9", "diesel", "5000"],
    ["Doosan", "G25N-7", "lpg", "5000"],
    ["Hyundai", "18BT-9", "electric", "3500"],
  ] as const;
  const customers = ["Penobscot Paper Co.", "Bangor Building Supply", "Downeast Seafood Distributors", "Kennebec Cold Storage"];
  return Array.from({ length: n }, (_, i) => {
    const [make, model, fuel, capacity] = makes[i % makes.length] ?? makes[0];
    return {
      customer_name: customers[i % customers.length] ?? "",
      card_date: `2024-0${(i % 9) + 1}-1${i % 10}`,
      mechanic: i % 2 ? "Dave R." : "Sam W.",
      condition: "used",
      hour_meter: String(3000 + i * 811),
      unit_make: make,
      unit_model: model,
      unit_serial: `${make === "Doosan" ? "FGA25" : "HHKH"}-${tag}${String(i).padStart(3, "0")}`,
      fuel_type: fuel,
      capacity_lbs: capacity,
      mast_make: make,
      mast_type: "TF470",
      forks: "1.75 x 4 x 48 STD; 1.75 x 4 x 48 STD",
      tire_drive_size: "8.15-15",
      tire_steer_size: "6.50-10",
      source_image_filename: i === 0 ? `card-${tag}-000.png` : "",
    };
  });
}

let draft: Batch;
let imported: Batch;
let undone: Batch;
let importedUnitId = "";

async function makeBatch(request: APIRequestContext, name: string, rows: Record<string, string>[], scan?: Buffer): Promise<Batch> {
  const headers = await csrfHeaders(request);
  const res = await request.post("/api/v1/imports/batches", {
    headers,
    multipart: { file: { name, mimeType: "text/csv", buffer: csv(rows) } },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const batch = (await res.json()) as Batch;
  const file = rows.find((r) => r.source_image_filename)?.source_image_filename;
  if (scan && file) {
    const up = await request.post(`/api/v1/imports/batches/${batch.id}/files`, {
      headers,
      multipart: { file: { name: file, mimeType: "image/png", buffer: scan } },
    });
    expect(up.ok(), await up.text()).toBeTruthy();
    await request.post(`/api/v1/imports/batches/${batch.id}/validate`, { headers });
  }
  return batch;
}

async function apply(request: APIRequestContext, batch: Batch, body: Record<string, unknown> = {}) {
  const res = await request.post(`/api/v1/imports/batches/${batch.id}/apply`, { headers: await csrfHeaders(request), data: body });
  expect(res.ok(), await res.text()).toBeTruthy();
}

test.beforeAll(async ({ playwright }) => {
  const request = await playwright.request.newContext({ baseURL: BASE, storageState: authFile("sales") });
  const tag = Date.now().toString(36).slice(-5).toUpperCase();

  // A scanned card: borrow the demo unit's sample scan.
  const units = (await (await request.get("/api/v1/units?scope=all&q=FGA25-70988")).json()) as { results: { id: string }[] };
  const files = (await (await request.get(`/api/v1/units/${units.results[0]?.id}/files`)).json()) as { id: string; kind: string }[];
  const scanFile = files.find((f) => f.kind === "scanned_card");
  const scan = scanFile ? await (await request.get(`/api/v1/unit-files/${scanFile.id}/content`)).body() : undefined;

  const done = cards(`F${tag}`, 12);
  imported = await makeBatch(request, "unit-cards-february.csv", done, scan);
  await apply(request, imported);
  const rows = (await (await request.get(`/api/v1/imports/batches/${imported.id}/rows`)).json()) as { results: { unit: string | null }[] };
  importedUnitId = rows.results[0]?.unit ?? "";

  undone = await makeBatch(request, "test-cards.csv", cards(`U${tag}`, 3));
  await apply(request, undone);
  await request.post(`/api/v1/imports/batches/${undone.id}/undo`, { headers: await csrfHeaders(request) });

  draft = await makeBatch(request, "unit-cards-march.csv", [
    ...cards(`M${tag}`, 6),
    // Already in the DMS: the card has more detail, so this is an update.
    { unit_serial: "FGA25-70988", unit_make: "Doosan", unit_model: "G25N-7", engine_serial: "K25-118734", mechanic: "Dave R.", customer_name: "Penobscot Paper Co." },
    // Same as the February import: no changes.
    { ...done[1] },
    // Problems the preview should explain.
    { unit_make: "Hyundai", unit_model: "35LN-9A", customer_name: "Pat Murphy", hour_meter: "4,210" },
    { ...cards(`X${tag}`, 1)[0], unit_serial: "1.23457E+12" },
    { ...cards(`Y${tag}`, 1)[0], capacity_lbs: "2.5 ton", customer_name: "Bangor Bldg Supply" },
  ]);
  await request.dispose();

  // One named key for the API keys page.
  const admin = await playwright.request.newContext({ baseURL: BASE, storageState: authFile("admin") });
  const keys = (await (await admin.get("/api/v1/admin/api-keys")).json()) as { name: string }[];
  if (!keys.some((k) => k.name === "Card scanner tablet")) {
    await admin.post("/api/v1/admin/api-keys", { headers: await csrfHeaders(admin), data: { name: "Card scanner tablet" } });
  }
  await admin.dispose();
});

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      const shot = shooter(OUT, viewport, theme);

      test("imports list and states", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/imports");
        await expect(page.getByText("unit-cards-march.csv").filter({ visible: true }).first()).toBeVisible();
        await shot(page, "imports");
        await page.goto("/");
        await expect(page.getByText("Import unit cards")).toBeVisible();
        await shot(page, "dashboard-sales");
        await page.context().close();

        const empty = await newPage(browser, viewport, theme, authFile("sales"));
        await empty.route("**/api/v1/imports/batches?*", (route) => route.fulfill({ json: { count: 0, next: null, previous: null, results: [] } }));
        await empty.goto("/imports");
        await expect(empty.getByText("No imports yet")).toBeVisible();
        await shot(empty, "imports-empty");
        await empty.context().close();

        const slow = await newPage(browser, viewport, theme, authFile("sales"));
        await slow.route("**/api/v1/imports/batches?*", async () => {
          await new Promise(() => undefined);
        });
        await slow.goto("/imports");
        await expect(slow.getByRole("status").filter({ hasText: "Loading" }).first()).toBeAttached();
        await slow.screenshot({ path: `${OUT}/imports-loading-${viewport}-${theme}.png`, animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("sales"));
        await broken.route("**/api/v1/imports/batches?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/imports");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "imports-error");
        await broken.context().close();
      });

      test("new import", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto("/imports/new");
        await expect(page.getByRole("heading", { name: "New import", level: 1 })).toBeVisible();
        await shot(page, "import-new");

        await page
          .locator('input[type="file"][accept=".csv,text/csv"]')
          .setInputFiles({ name: "Cards.xlsx", mimeType: "application/vnd.ms-excel", buffer: Buffer.from("PK") });
        await expect(page.getByRole("alert")).toContainText("CSV UTF-8");
        await shot(page, "import-new-excel-error", false);

        await page
          .locator('input[type="file"][accept=".csv,text/csv"]')
          .setInputFiles({ name: "unit-cards-april.csv", mimeType: "text/csv", buffer: csv(cards("APR", 40)) });
        await page.locator('input[type="file"][multiple]').setInputFiles(
          Array.from({ length: 5 }, (_, i) => ({ name: `card-04${String(i + 10)}.jpg`, mimeType: "image/jpeg", buffer: Buffer.alloc(180_000 + i * 9000) })),
        );
        await expect(page.getByText("5 scans")).toBeVisible();
        await shot(page, "import-new-filled");
        await page.context().close();
      });

      test("preview, results and undo", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("sales"));
        await page.goto(`/imports/${draft.id}`);
        await expect(page.getByRole("button", { name: /^Import \d+ units$/ })).toBeVisible();
        await shot(page, "import-preview");

        await page.getByRole("tab", { name: "Errors" }).click();
        await expect(page.getByText("Needs a unit serial (or a stock number).").first()).toBeVisible();
        await page.getByLabel(/Skip the \d+ rows with errors/).check();
        await shot(page, "import-preview-errors");

        await page.getByRole("tab", { name: "Warnings" }).click();
        await expect(page.getByText(/looks like “Bangor Building Supply”/)).toBeVisible();
        await shot(page, "import-preview-warnings");
        await page.context().close();

        const done = await newPage(browser, viewport, theme, authFile("sales"));
        await done.goto(`/imports/${imported.id}`);
        await expect(done.getByRole("button", { name: "Undo this import" })).toBeVisible();
        await shot(done, "import-imported");
        await done.getByRole("button", { name: "Undo this import" }).click();
        await expect(done.getByRole("alertdialog")).toBeVisible();
        await shot(done, "import-undo-confirm", false);
        await done.getByRole("alertdialog").getByRole("button", { name: "Cancel" }).click();

        await done.goto(`/imports/${undone.id}`);
        await expect(done.getByText("Undone", { exact: true }).first()).toBeVisible();
        await shot(done, "import-undone");

        // While an import runs in the background the page follows along.
        await done.route(`**/api/v1/imports/batches/${draft.id}`, async (route) => {
          const res = await route.fetch();
          const body = (await res.json()) as Record<string, unknown>;
          await route.fulfill({ json: { ...body, status: "importing", status_label: "Importing" } });
        });
        await done.goto(`/imports/${draft.id}`);
        await expect(done.getByText(/Importing… This page updates by itself/)).toBeVisible();
        await shot(done, "import-in-progress", false);

        await done.goto(`/units/${importedUnitId}`);
        await expect(done.getByText("Original unit card").first()).toBeVisible();
        await shot(done, "unit-from-import");
        await done.context().close();
      });

      test("api keys", async ({ browser }) => {
        const page: Page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/admin/api-keys");
        await expect(page.getByRole("heading", { name: "API keys", level: 1 })).toBeVisible();
        await shot(page, "api-keys");

        await page.getByRole("button", { name: "New key" }).click();
        await page.getByRole("dialog").getByLabel("Name").fill("Card scanner tablet");
        // Show the "copy it now" step without creating a real key.
        await page.route("**/api/v1/admin/api-keys", (route) =>
          route.request().method() === "POST"
            ? route.fulfill({
                status: 201,
                json: {
                  id: "00000000-0000-0000-0000-000000000001",
                  name: "Card scanner tablet",
                  prefix: "mmh_Q3vX9k",
                  created_at: new Date().toISOString(),
                  created_by_name: "Pat Owner",
                  last_used_at: null,
                  revoked_at: null,
                  is_active: true,
                  key: "mmh_Q3vX9kLm2TzR8pWq4NcY7bHd1sJf6Ga0eUoKiVxBnM5",
                },
              })
            : route.fallback(),
        );
        await page.getByRole("dialog").getByRole("button", { name: "Create key" }).click();
        await expect(page.getByTestId("new-api-key")).toBeVisible();
        await shot(page, "api-key-created", false);
        await page.context().close();
      });
    });
  }
}
