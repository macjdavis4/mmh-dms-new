import { expect, type Page, test } from "@playwright/test";

import { authFile } from "./helpers";

async function pdfFrom(page: Page, href: string | null) {
  expect(href).toBeTruthy();
  const res = await page.request.get(href ?? "");
  expect(res.status()).toBe(200);
  expect(res.headers()["content-type"]).toBe("application/pdf");
  expect((await res.body()).subarray(0, 4).toString()).toBe("%PDF");
  return res;
}

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("spec sheet with or without the asking price", async ({ page }) => {
    await page.goto("/units");
    await page.getByRole("list", { name: "Units" }).getByRole("link", { name: /35LN-9A/ }).first().click();
    await page.getByRole("button", { name: "Spec sheet" }).click();
    const plain = page.getByRole("menuitem", { name: "Spec sheet", exact: true });
    const priced = page.getByRole("menuitem", { name: "Spec sheet with asking price" });
    await expect(plain).toHaveAttribute("target", "_blank");
    await pdfFrom(page, await plain.getAttribute("href"));
    const res = await pdfFrom(page, await priced.getAttribute("href"));
    expect(res.headers()["content-disposition"]).toMatch(/^inline; filename=".+-spec-sheet\.pdf"$/);
  });
});

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("print a work order; no priced spec sheet", async ({ page }) => {
    const found = (await (await page.request.get("/api/v1/work-orders?scope=all&q=Mast%20chatters")).json()) as { results: { id: string }[] };
    await page.goto(`/service/${found.results[0]?.id}`);
    const print = page.getByRole("link", { name: "Print" });
    await expect(print).toHaveAttribute("target", "_blank");
    const res = await pdfFrom(page, await print.getAttribute("href"));
    expect(res.headers()["content-disposition"]).toMatch(/filename="WO-\d+\.pdf"/);

    await page.getByRole("link", { name: /Hyundai 70D-9/ }).click();
    const sheet = page.getByRole("link", { name: "Spec sheet" });
    await pdfFrom(page, await sheet.getAttribute("href"));
    const href = (await sheet.getAttribute("href")) ?? "";
    expect((await page.request.get(`${href}?price=1`)).status()).toBe(403);
  });
});
