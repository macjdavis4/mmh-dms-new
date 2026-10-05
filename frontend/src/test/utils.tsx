import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import { ThemeProvider } from "@/lib/theme";

export function renderWithProviders(ui: ReactElement, { path = "/" }: { path?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [
      { path: "*", element: ui },
    ],
    { initialEntries: [path] },
  );
  return {
    client,
    router,
    ...render(
      <ThemeProvider>
        <QueryClientProvider client={client}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </ThemeProvider>,
    ),
  };
}

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown };

/** Replace fetch with a router of fake API responses. */
export function mockApi(handler: Handler) {
  const spy = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const { status = 200, body } = handler(url, init);
    return Promise.resolve(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}
