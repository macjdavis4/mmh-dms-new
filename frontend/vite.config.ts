/// <reference types="vitest/config" />
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

// Built files are served by Django (WhiteNoise) under /static/, from the same
// origin as the API. In development Vite proxies the API to Django.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/" : "/",
  plugins: [react(), tailwindcss()],
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
