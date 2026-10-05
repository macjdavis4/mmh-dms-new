import { execFileSync } from "node:child_process";
import path from "node:path";

import { test as setup } from "@playwright/test";

import { apiLogin, authFile, USERS } from "./helpers";

setup("seed demo data and sign in each role", async ({ playwright, baseURL }) => {
  if (process.env.E2E_SEED_CMD !== "skip") {
    const backend = path.resolve(import.meta.dirname, "../../backend");
    const python = process.env.E2E_PYTHON ?? path.join(backend, ".venv/bin/python");
    execFileSync(python, ["manage.py", "seed_dev"], {
      cwd: backend,
      env: { ...process.env, DJANGO_SETTINGS_MODULE: process.env.DJANGO_SETTINGS_MODULE ?? "config.settings.e2e" },
      stdio: "inherit",
    });
  }
  const url = baseURL ?? "http://localhost:8000";
  for (const role of ["admin", "sales", "service", "parts", "viewer"] as const) {
    const request = await playwright.request.newContext({ baseURL: url });
    await apiLogin(request, url, USERS[role]);
    await request.storageState({ path: authFile(role) });
    await request.dispose();
  }
});
