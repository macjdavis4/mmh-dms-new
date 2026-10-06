/// <reference types="vitest/config" />
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** Writes sw.js (from sw/service-worker.js) listing every built file, so the
 * app opens without a connection. Django serves it at /sw.js. No library. */
function serviceWorker(): Plugin {
  return {
    name: "mmh-service-worker",
    apply: "build",
    generateBundle(_options, bundle) {
      const files = Object.keys(bundle)
        .filter((name) => !name.endsWith(".map") && name !== "index.html")
        .sort();
      const assets = ["/static/favicon.svg", ...files.map((name) => `/static/${name}`)];
      const version = createHash("sha256").update(assets.join("\n")).digest("hex").slice(0, 12);
      const source = readFileSync(path.resolve(__dirname, "sw/service-worker.js"), "utf8")
        .replace("__VERSION__", version)
        .replace("__ASSETS__", JSON.stringify(assets));
      this.emitFile({ type: "asset", fileName: "sw.js", source });
    },
  };
}

// Built files are served by Django (WhiteNoise) under /static/, from the same
// origin as the API. In development Vite proxies the API to Django.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/" : "/",
  plugins: [react(), tailwindcss(), serviceWorker()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  build: {
    outDir: "../backend/frontend_dist",
    emptyOutDir: true,
    sourcemap: true,
    target: "es2022",
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/healthz": backend,
      "/readyz": backend,
      "/django-admin": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    coverage: { provider: "v8", reporter: ["text-summary", "lcov"], include: ["src/**"] },
  },
}));
