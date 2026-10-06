import "@/styles/index.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { readRuntimeConfig } from "@/app/config";
import { makeQueryClient } from "@/app/queryClient";
import { router } from "@/app/router";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { applyTheme, readStoredTheme, ThemeProvider } from "@/lib/theme";

applyTheme(readStoredTheme()); // before first paint, to avoid a flash of the wrong theme

const config = readRuntimeConfig();
if (config.sentryDsn) {
  // Loaded only when error reporting is configured, to keep the first load small.
  void import("@sentry/react").then((Sentry) =>
    Sentry.init({ dsn: config.sentryDsn, environment: config.env, release: config.version, tracesSampleRate: 0 }),
  );
}

// Keep the app on the device so it opens without a connection (Phase 13).
// Production builds only: the dev server serves files on the fly.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);
  });
}

const queryClient = makeQueryClient();
const root = document.getElementById("root");
if (!root) throw new Error("#root missing");

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <RouterProvider router={router} />
          <Toaster position="top-center" richColors closeButton />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
