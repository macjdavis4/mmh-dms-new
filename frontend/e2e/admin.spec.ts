import { expect, test } from "@playwright/test";

import { authFile, watchConsole } from "./helpers";

test.use({ storageState: authFile("admin") });

test("add, edit, remove and restore a user", async ({ page }) => {
  const problems = watchConsole(page);
  const email = `temp.${Date.now()}@mmh.test`;
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Add user" }).click();
  const dialog = page.getByRole("dialog");

  // Inline validation before anything is sent.
  await dialog.getByRole("button", { name: "Add user" }).click();
  await expect(dialog.getByText("Enter a first name.")).toBeVisible();
  await expect(dialog.getByText("Set a starting password.")).toBeVisible();

  await dialog.getByLabel("First name").fill("Taylor");
  await dialog.getByLabel("Last name").fill("Temp");
  await dialog.getByLabel("Email").fill(email);
  await dialog.getByRole("combobox", { name: "Role" }).click();
  await page.getByRole("option", { name: "Parts" }).click();
  await dialog.getByLabel("Starting password").fill("Pallet-Jack-Strong-1");
  await dialog.getByRole("button", { name: "Add user" }).click();
  await expect(page.getByText("Taylor Temp was added")).toBeVisible();

  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row.getByText("Parts")).toBeVisible();

  // Remove, with confirmation, then undo.
  await row.getByRole("button", { name: /Actions for/ }).click();
  await page.getByRole("menuitem", { name: "Remove user" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Remove user" }).click();
  await expect(page.getByText("Taylor Temp was removed")).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: email })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("row").filter({ hasText: email })).toHaveCount(1);
  expect(problems).toEqual([]);
});

test("maintenance banner and read-only mode", async ({ page }) => {
  await page.goto("/admin/settings");
  await page.getByLabel("Message").fill("Updates tonight 7–8 PM. Save your work.");
  await page.getByRole("combobox", { name: "Style" }).click();
  await page.getByRole("option", { name: /Warning/ }).click();
  await page.getByRole("button", { name: "Save banner" }).click();
  await expect(page.getByRole("status").getByText("Updates tonight 7–8 PM. Save your work.")).toBeVisible();

  await page.getByRole("switch").click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Turn on" }).click();
  await expect(page.getByText(/Read-only mode: you can look things up/)).toBeVisible();

  // Writes are refused while read-only.
  await page.goto("/admin/users");
  await page.getByRole("button", { name: "Add user" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("First name").fill("Blocked");
  await dialog.getByLabel("Email").fill("blocked@mmh.test");
  await dialog.getByLabel("Starting password").fill("Pallet-Jack-Strong-1");
  await dialog.getByRole("button", { name: "Add user" }).click();
  await expect(dialog.getByRole("alert")).toContainText("read-only mode");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  // Turn everything back off.
  await page.goto("/admin/settings");
  await page.getByRole("switch").click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Turn off" }).click();
  await page.getByRole("button", { name: "Remove banner" }).click();
  await expect(page.getByText(/Read-only mode: you can look things up/)).toHaveCount(0);
});

test("audit log lists recent changes", async ({ page }) => {
  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { name: "Audit log", level: 1 })).toBeVisible();
  await expect(page.getByText("Signed in").filter({ visible: true }).first()).toBeVisible();
});

test("dashboard shows system health to admins", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
  await expect(page.getByText("Connected")).toBeVisible();
});
