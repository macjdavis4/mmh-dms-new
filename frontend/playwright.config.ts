import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8000";
// The cloud sandbox ships its own Chromium; CI installs Playwright's.
const executablePath = process.env.PW_CHROMIUM_PATH;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [
    { name: "setup", testMatch: /global\.setup\.ts/ },
    { name: "e2e", testMatch: /.*\.spec\.ts/, testIgnore: /screenshots\.spec\.ts/, dependencies: ["setup"] },
    { name: "screenshots", testMatch: /screenshots\.spec\.ts/, dependencies: ["setup"], timeout: 120_000 },
  ],
});
