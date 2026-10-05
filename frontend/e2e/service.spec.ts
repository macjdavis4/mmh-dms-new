import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.describe("as a mechanic (service)", () => {
  test.use({ storageState: authFile("service") });

  test("open a work order from a unit, log time, and complete it", async ({ page }) => {
    const problems = watchConsole(page);
    const job = `Horn inoperative ${Date.now()}`;
    await page.goto("/units?scope=customer");
    await page.getByRole("list", { name: "Units" }).getByRole("link", { name: /70D-9/ }).click();
    await page.getByRole("link", { name: "New work order" }).click();

    // The unit is already chosen; the customer comes from its owner.
    await expect(page.getByText("HHKHFV30K00057")).toBeVisible();
    await page.getByRole("button", { name: "Open work order" }).click();
    await expect(page.getByText("Describe the problem or the job.")).toBeVisible();
    await page.getByLabel("What's wrong (complaint)").fill(job);
    await page.getByLabel("Hour meter (optional)").fill("9400");
    await page.getByRole("button", { name: "Open work order" }).click();

    await expect(page).toHaveURL(/\/service\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(/^WO-\d+$/);
    await expect(page.getByText("Katahdin Lumber")).toBeVisible();
    await expect(page.getByText("9,400 h")).toBeVisible();

    await page.getByRole("button", { name: "Start work" }).click();
    await expect(page.getByText("In progress", { exact: true }).first()).toBeVisible();

    await page.getByLabel("Hours", { exact: true }).fill("1.5");
    await page.getByLabel("What was done (optional)").fill("Traced wiring");
    await page.getByRole("button", { name: "Add time" }).click();
    await expect(page.getByRole("list", { name: "Labor lines" }).getByText("Traced wiring")).toBeVisible();

    // Completing needs the correction.
    await page.getByRole("button", { name: "Complete" }).click();
    await expect(page.getByText("Fill in what was done (correction) first.")).toBeVisible();
    await page.getByLabel("Correction").fill("Replaced horn relay; tested OK.");
    await page.getByRole("button", { name: "Complete" }).click();
    await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();

    // It shows in the unit's service history and in search.
    await page.getByRole("link", { name: /Hyundai 70D-9/ }).click();
    await expect(page.getByRole("list", { name: "Work orders for this unit" }).getByText(job)).toBeVisible();
    expect(problems).toEqual([]);
  });

  test("put a job on hold with a reason", async ({ page }) => {
    await page.goto("/service/new");
    await page.getByLabel("Unit", { exact: true }).fill("HHKHHL03");
    await page.getByRole("option", { name: /30L-9A/ }).click();
    await page.getByLabel("What's wrong (complaint)").fill(`Check brakes ${Date.now()}`);
    await page.getByRole("button", { name: "Open work order" }).click();
    await page.getByRole("button", { name: "Put on hold" }).click();
    await page.getByRole("dialog").getByLabel("Waiting for").fill("Brake shoes on order");
    await page.getByRole("dialog").getByRole("button", { name: "Put on hold" }).click();
    await expect(page.getByText("On hold:")).toBeVisible();
    await expect(page.getByText("Brake shoes on order")).toBeVisible();
  });

  test("my work orders and the open list", async ({ page }) => {
    await page.goto("/service");
    await expect(page.getByRole("tab", { name: "Open" })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("button", { name: "Mine" }).click();
    await expect(page.getByText(/Mast chatters/).filter({ visible: true }).first()).toBeVisible();
    await page.getByRole("tab", { name: "Completed" }).click();
    await expect(page.getByText(/250-hour service/).filter({ visible: true }).first()).toBeVisible();
  });
});

test.describe("as sales", () => {
  test.use({ storageState: authFile("sales") });

  test("can read work orders but not change them", async ({ page }) => {
    await page.goto("/service");
    await expect(page.getByRole("link", { name: "New work order" })).toHaveCount(0);
    await page.getByRole("searchbox", { name: "Search work orders" }).fill("mast");
    await page.getByRole("link", { name: /^WO-/ }).filter({ visible: true }).first().click();
    await expect(page.getByRole("button", { name: "Start work" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Add time" })).toHaveCount(0);
    await expect(page.getByLabel("Complaint")).toHaveAttribute("readonly", "");
  });
});
