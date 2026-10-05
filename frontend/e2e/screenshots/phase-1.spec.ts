/**
 * UI screenshots for the phase PR: every new or changed screen at desktop,
 * tablet and phone widths, in light and dark mode, plus key states.
 *
 *   SCREENSHOT_PHASE=1 npx playwright test --project=screenshots
 *
 * Kept as the record of how the phase 1 pictures were made. Later phases
 * changed some of these screens (units is no longer "coming soon").
 */
import path from "node:path";

import { type APIRequestContext, type Browser, expect, type Page, test } from "@playwright/test";

import { apiLogin, authFile, PASSWORD, USERS } from "../helpers";

const OUT = process.env.SCREENSHOT_DIR ?? path.resolve(import.meta.dirname, "../../../docs/screenshots/phase-1");

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 1024, height: 768 },
  phone: { width: 390, height: 844 },
} as const;
const THEMES = ["light", "dark"] as const;

type Viewport = keyof typeof VIEWPORTS;
type Theme = (typeof THEMES)[number];

async function newPage(
  browser: Browser,
  viewport: Viewport,
  theme: Theme,
  storageState?: string,
): Promise<Page> {
  const context = await browser.newContext({
    viewport: VIEWPORTS[viewport],
    colorScheme: theme,
    reducedMotion: "reduce",
    deviceScaleFactor: 1,
    ...(storageState ? { storageState } : {}),
  });
  await context.addInitScript((t) => window.localStorage.setItem("mmh-theme", t), theme);
  return context.newPage();
}

async function shot(page: Page, name: string, viewport: Viewport, theme: Theme, fullPage = true) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(OUT, `${name}-${viewport}-${theme}.png`), fullPage, animations: "disabled" });
}

async function csrfHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  await request.get("/api/v1/auth/csrf");
  const cookie = (await request.storageState()).cookies.find((c) => c.name === "mmh_csrftoken");
  return { "X-CSRFToken": cookie?.value ?? "", Referer: "http://localhost:8000" };
}

for (const viewport of Object.keys(VIEWPORTS) as Viewport[]) {
  for (const theme of THEMES) {
    test.describe(`${viewport} ${theme}`, () => {
      test("sign-in screens", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme);
        await page.goto("/login");
        await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
        await shot(page, "login", viewport, theme);

        await page.getByRole("button", { name: "Sign in" }).click();
        await shot(page, "login-validation", viewport, theme);

        // A made-up address, so repeated runs never lock a real demo account.
        await page.getByLabel("Email").fill("someone@mmh.test");
        await page.getByLabel("Password").fill("wrong-password");
        await page.getByRole("button", { name: "Sign in" }).click();
        await expect(page.getByRole("alert")).toBeVisible();
        await shot(page, "login-error", viewport, theme);

        await page.getByLabel("Email").fill(USERS.admin2);
        await page.getByLabel("Password").fill(PASSWORD);
        await page.getByRole("button", { name: "Sign in" }).click();
        await expect(page.getByRole("heading", { name: "Enter your code" })).toBeVisible();
        await shot(page, "login-2fa-code", viewport, theme);
        await page.context().close();
      });

      test("two-factor setup", async ({ browser, playwright }) => {
        const request = await playwright.request.newContext({ baseURL: "http://localhost:8000" });
        await apiLogin(request, "http://localhost:8000", USERS.newadmin);
        const state = await request.storageState();
        await request.dispose();
        const context = await browser.newContext({
          viewport: VIEWPORTS[viewport],
          colorScheme: theme,
          reducedMotion: "reduce",
          storageState: state,
        });
        await context.addInitScript((t) => window.localStorage.setItem("mmh-theme", t), theme);
        const page = await context.newPage();
        await page.goto("/setup-2fa");
        await expect(page.getByRole("img", { name: /QR code/ })).toBeVisible();
        await shot(page, "setup-2fa", viewport, theme);

        // Show the recovery-codes step without changing the demo account.
        await page.route("**/api/v1/auth/2fa/confirm", (route) =>
          route.fulfill({
            json: {
              recovery_codes: ["3f9a-0c71", "b2e4-91d0", "7c1e-a5f2", "e08b-4d3c", "51aa-c9e7", "d4f0-2b68", "9e37-f1a4", "06cd-83b5", "a7b2-5e19", "c3d8-7fa0"],
              authenticated: true,
              user: { id: "x", email: USERS.newadmin, first_name: "Jordan", last_name: "Manager", full_name: "Jordan Manager", role: "admin", role_label: "Admin", can_see_pricing: true },
              two_factor: { enabled: true, verified: true, required: true, setup_needed: false, recovery_codes_left: 10 },
            },
          }),
        );
        await page.getByLabel("6-digit code").fill("123456");
        await page.getByRole("button", { name: "Turn on" }).click();
        await expect(page.getByText("Save your recovery codes")).toBeVisible();
        await shot(page, "setup-2fa-recovery-codes", viewport, theme);
        await context.close();
      });

      test("dashboard, search and placeholders", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/");
        await expect(page.getByText("Connected")).toBeVisible();
        await shot(page, "dashboard-admin", viewport, theme);

        if (viewport === "phone") {
          await page.getByRole("button", { name: "Open menu" }).click();
          await expect(page.getByRole("dialog").getByRole("navigation")).toBeVisible();
          await shot(page, "menu-drawer", viewport, theme, false);
          await page.keyboard.press("Escape");
          await page.getByRole("button", { name: "Search", exact: true }).click();
          await page.getByRole("dialog").getByRole("searchbox").fill("35LN-9A");
        } else {
          await page.getByRole("combobox").fill("35LN-9A");
        }
        await expect(page.getByText("No matches for “35LN-9A”.")).toBeVisible();
        await shot(page, "global-search", viewport, theme, false);

        await page.goto("/units");
        await expect(page.getByRole("heading", { name: "Arrives in phase 2" })).toBeVisible();
        await shot(page, "coming-soon-units", viewport, theme);

        await page.goto("/no-such-page");
        await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
        await shot(page, "not-found", viewport, theme);
        await page.context().close();

        const sales = await newPage(browser, viewport, theme, authFile("sales"));
        await sales.goto("/");
        await expect(sales.getByRole("heading", { level: 1 })).toContainText("Casey");
        await shot(sales, "dashboard-sales", viewport, theme);
        await sales.context().close();
      });

      test("users", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/admin/users");
        await expect(page.getByText(USERS.sales).filter({ visible: true }).first()).toBeVisible();
        await shot(page, "users", viewport, theme);

        await page.getByRole("searchbox", { name: "Search users" }).fill("nobody-by-this-name");
        await expect(page.getByText("No users match")).toBeVisible();
        await shot(page, "users-empty", viewport, theme);

        await page.getByRole("button", { name: "Add user" }).click();
        const dialog = page.getByRole("dialog");
        await dialog.getByRole("button", { name: "Add user" }).click();
        await expect(dialog.getByText("Enter a first name.")).toBeVisible();
        await shot(page, "user-form-errors", viewport, theme, false);

        await dialog.getByLabel("First name").fill("Morgan");
        await dialog.getByLabel("Last name").fill("Lift");
        await dialog.getByLabel("Email").fill("morgan@mmh.test");
        await dialog.getByLabel("Mobile phone (optional)").fill("207-555-0142");
        await dialog.getByLabel("Starting password").fill("Pallet-Jack-Strong-1");
        await shot(page, "user-form-filled", viewport, theme, false);
        await dialog.getByRole("button", { name: "Cancel" }).click();
        await page.context().close();

        // Loading and error states.
        const slow = await newPage(browser, viewport, theme, authFile("admin"));
        await slow.route("**/api/v1/admin/users?*", async () => {
          await new Promise(() => undefined); // never answers
        });
        await slow.goto("/admin/users");
        await expect(slow.getByRole("status").filter({ hasText: "Loading" })).toBeAttached();
        await slow.screenshot({ path: path.join(OUT, `users-loading-${viewport}-${theme}.png`), animations: "disabled" });
        await slow.context().close();

        const broken = await newPage(browser, viewport, theme, authFile("admin"));
        await broken.route("**/api/v1/admin/users?*", (route) => route.fulfill({ status: 500, body: "" }));
        await broken.goto("/admin/users");
        await expect(broken.getByText("We couldn't load this list.")).toBeVisible({ timeout: 15_000 });
        await shot(broken, "users-error", viewport, theme);
        await broken.context().close();
      });

      test("site settings, banner and read-only mode", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/admin/settings");
        await expect(page.getByText("Read-only mode is off")).toBeVisible();
        await shot(page, "site-settings", viewport, theme);

        const headers = await csrfHeaders(page.request);
        try {
          await page.request.patch("/api/v1/admin/site-settings", {
            headers,
            data: {
              read_only_mode: true,
              banner_message: "Scheduled maintenance Saturday 7–8 AM. The system will be read-only.",
              banner_level: "warning",
            },
          });
          await page.goto("/");
          await expect(page.getByText(/Read-only mode: you can look things up/)).toBeVisible();
          await shot(page, "dashboard-maintenance-read-only", viewport, theme);
          await page.goto("/admin/settings");
          await expect(page.getByText("Read-only mode is ON")).toBeVisible();
          await shot(page, "site-settings-read-only-on", viewport, theme);
        } finally {
          await page.request.patch("/api/v1/admin/site-settings", {
            headers,
            data: { read_only_mode: false, banner_message: "", banner_level: "info" },
          });
        }
        await page.context().close();
      });

      test("audit log and account", async ({ browser }) => {
        const page = await newPage(browser, viewport, theme, authFile("admin"));
        await page.goto("/admin/audit");
        await expect(page.getByText("Signed in").filter({ visible: true }).first()).toBeVisible();
        await shot(page, "audit-log", viewport, theme, false);

        await page.goto("/account");
        await expect(page.getByRole("heading", { name: "My account", level: 1 })).toBeVisible();
        await shot(page, "account", viewport, theme);
        await page.context().close();
      });
    });
  }
}
