import { QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/lib/api";

export function makeQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        // Session expired or signed out elsewhere: refresh "me" so the app
        // sends the person back to the sign-in page.
        if (error instanceof ApiError && error.status === 401) {
          void client.invalidateQueries({ queryKey: ["auth", "me"] });
        }
      },
    }),
    defaultOptions: {
      queries: {
        retry: (count, error) => !(error instanceof ApiError && error.status < 500 && error.status !== 0) && count < 2,
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false },
    },
  });
  return client;
}
