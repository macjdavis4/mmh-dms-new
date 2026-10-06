import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8000";
// The cloud sandbox ships its own Chromium; CI installs Playwright's.
const executablePath = process.env.PW_CHROMIUM_PATH;
// Screenshots are taken for one phase at a time (default: the current one).
const screenshotPhase = process.env.SCREENSHOT_PHASE ?? "11";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  use: {
    baseURL,
    // The shop's time zone, as on the server: otherwise "today" in the
    // browser is tomorrow for the server between 8 pm and midnight Eastern.
    timezoneId: "America/New_York",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [
    { name: "setup", testMatch: /global\.setup\.ts/ },
    { name: "e2e", testMatch: /.*\.spec\.ts/, testIgnore: /screenshots\//, dependencies: ["setup"] },
    {
      name: "screenshots",
      testMatch: new RegExp(`screenshots/phase-${screenshotPhase}\\.spec\\.ts$`),
      dependencies: ["setup"],
      timeout: 180_000,
    },
  ],
});
