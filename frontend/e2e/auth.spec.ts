import { expect, test } from "@playwright/test";

import { DEMO_TOTP_SECRET, PASSWORD, totp, USERS, watchConsole } from "./helpers";

test.describe("sign in", () => {
  test("staff without 2FA sign in and land on the dashboard", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await page.getByLabel("Email").fill(USERS.sales);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Casey");
    await expect(page.getByRole("navigation", { name: "Main" }).getByText("Sales")).toBeVisible();
    await expect(page.getByRole("link", { name: "Users" })).toHaveCount(0);
    expect(problems).toEqual([]);
  });

  test("wrong password shows a plain message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.viewer);
    await page.getByLabel("Password").fill("not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect.");
  });

  test("admins enter a code from their authenticator app", async ({ page }) => {
    await page.goto("/login?next=/admin/users");
    await page.getByLabel("Email").fill(USERS.admin2);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("heading", { name: "Enter your code" })).toBeVisible();
    await page.getByLabel("Code").fill(totp(DEMO_TOTP_SECRET, 1));
    await page.getByRole("button", { name: "Verify and sign in" }).click();
    await expect(page).toHaveURL(/\/admin\/users$/);
    await expect(page.getByRole("heading", { name: "Users", level: 1 })).toBeVisible();
  });

  test("a new admin must set up 2FA before anything else", async ({ page }) => {
    const problems = watchConsole(page);
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.newadmin);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/setup-2fa$/);
    await expect(page.getByRole("img", { name: /QR code/ })).toBeVisible();

    // Going elsewhere bounces back to setup.
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/setup-2fa$/);

    await expect(page.getByTestId("totp-secret")).not.toHaveText("…");
    const secret = (await page.getByTestId("totp-secret").textContent()) ?? "";
    await page.getByLabel("6-digit code").fill(totp(secret.replace(/\s/g, "")));
    await page.getByRole("button", { name: "Turn on" }).click();
    await expect(page.getByRole("list", { name: "Recovery codes" }).getByRole("listitem")).toHaveCount(10);
    await page.getByRole("button", { name: /saved my codes/ }).click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Jordan");
    expect(problems).toEqual([]);
  });

  test("sign out", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(USERS.parts);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount/);
  });
});
