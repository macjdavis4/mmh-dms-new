import { useQuery } from "@tanstack/react-query";

import { api } from "./api";

export function useFlags() {
  return useQuery({
    queryKey: ["feature-flags"],
    queryFn: () => api<{ flags: Record<string, boolean> }>("/api/v1/feature-flags"),
    staleTime: 60_000,
  });
}

/** Missing flags count as on (flags exist to switch features off). */
export function isOn(flags: Record<string, boolean> | undefined, key: string | undefined): boolean {
  if (!key) return true;
  return flags?.[key] ?? true;
}
