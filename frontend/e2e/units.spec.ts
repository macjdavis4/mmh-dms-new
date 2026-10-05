import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

// A real 2x2 PNG; the server checks image contents, not just the name.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP438AARAwQCgAt7gX9iz9uhAAAAABJRU5ErkJggg==",
  "base64",
);

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("stock list shows prices and filters by condition", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/units");
    await expect(page.getByRole("heading", { name: "Units", level: 1 })).toBeVisible();
    await expect(page.getByRole("tab", { name: "In stock" })).toHaveAttribute("aria-selected", "true");
    const list = page.getByRole("list", { name: "Units" });
    await expect(list.getByText("$38,900", { exact: false })).toBeVisible();
    await expect(list.getByText("25LC-7A")).toHaveCount(0); // sold, so not in stock

    await page.goto("/units?condition=new");
    await expect(list.getByText("30L-9A")).toBeVisible();
    await expect(list.getByText("G25N-7")).toHaveCount(0);

    await page.goto("/units?scope=all&q=HHKHHC52");
    await expect(list.getByText("25LC-7A")).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("add a unit, see the duplicate serial warning, upload a photo", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/units/new");
    await expect(page.getByRole("heading", { name: "Add a unit", level: 1 })).toBeVisible();

    // An existing serial, typed with different punctuation, is flagged before saving.
    await page.getByRole("textbox", { name: "Serial number" }).fill("hhkhhn04-p00123");
    await expect(page.getByRole("alert").filter({ hasText: "This serial is already on" })).toBeVisible();

    const serial = `E2E${Date.now()}`;
    await page.getByRole("textbox", { name: "Serial number" }).fill(serial);
    await expect(page.getByText("This serial is already on")).toHaveCount(0);
    await page.getByLabel("Make", { exact: true }).fill("Hyundai");
    await page.getByLabel("Model", { exact: true }).fill("25L-9A");
    await page.getByLabel("Who owns it?").selectOption("dealer");
    await page.getByLabel("Hour meter").fill("1520");
    await page.getByRole("button", { name: "Add unit" }).click();

    await expect(page.getByRole("heading", { name: /Hyundai 25L-9A/, level: 1 })).toBeVisible();
    await expect(page.getByText("Maine Material Handling stock").first()).toBeVisible();
    await expect(page.getByText("1,520").first()).toBeVisible();

    await page.getByTestId("photo-input").setInputFiles({ name: "front.png", mimeType: "image/png", buffer: PNG });
    await expect(page.getByText("front.png uploaded")).toBeVisible();
    await expect(page.getByRole("list", { name: "Photos" }).getByRole("img")).toHaveCount(1);
    expect(problems).toEqual([]);
  });

  test("saving a duplicate serial is refused by the server", async ({ page }) => {
    await page.goto("/units/new");
    await page.getByRole("textbox", { name: "Serial number" }).fill("FGA25-71522");
    await page.getByLabel("Who owns it?").selectOption("dealer");
    await page.getByRole("button", { name: "Add unit" }).click();
    await expect(page.getByText(/already/i).first()).toBeVisible();
    await expect(page).toHaveURL(/\/units\/new$/);
  });
});

test.describe("as service", () => {
  test.use({ storageState: authFile("service") });

  test("prices are never shown", async ({ page }) => {
    const responses: string[] = [];
    page.on("response", async (res) => {
      if (res.url().includes("/api/v1/units")) responses.push(await res.text().catch(() => ""));
    });
    await page.goto("/units");
    await expect(page.getByRole("list", { name: "Units" })).toBeVisible();
    await expect(page.getByText("$38,900", { exact: false })).toHaveCount(0);
    await page.getByRole("list", { name: "Units" }).getByRole("link").first().click();
    await expect(page.getByRole("button", { name: "Add hours" })).toBeVisible();
    await expect(page.getByText(/Pricing/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Change owner" })).toHaveCount(0);
    for (const body of responses) {
      expect(body).not.toContain("asking_price");
      expect(body).not.toContain("\"cost\"");
    }
  });

  test("record an hour meter reading", async ({ page }) => {
    await page.goto("/units?scope=customer");
    await page.getByRole("list", { name: "Units" }).getByRole("link", { name: /70D-9/ }).click();
    await page.getByRole("button", { name: "Add hours" }).click();
    await page.getByRole("dialog").getByLabel("Hours").fill("99999");
    await page.getByRole("dialog").getByRole("button", { name: "Save reading" }).click();
    await expect(page.getByText("99,999").first()).toBeVisible();
  });
});

test.describe("as read-only", () => {
  test.use({ storageState: authFile("viewer") });

  test("the unit page has no edit actions", async ({ page }) => {
    await page.goto("/units");
    await expect(page.getByRole("link", { name: "Add unit" })).toHaveCount(0);
    await page.getByRole("list", { name: "Units" }).getByRole("link").first().click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit unit card" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add hours" })).toHaveCount(0);
  });
});
