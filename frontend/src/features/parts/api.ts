import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { Part, PartBin, PartFacets, PartRow, Role } from "@/lib/types";

const BASE = "/api/v1/parts";

export const partKeys = {
  all: ["parts"] as const,
  list: (params: string) => ["parts", "list", params] as const,
  detail: (id: string) => ["parts", "detail", id] as const,
  bins: ["parts", "bins"] as const,
};

// Mirrors apps/parts/views.py and serializers.py (the server enforces it).
export const canEditParts = (role: Role) => role === "admin" || role === "parts";
export const canSeePartCost = (role: Role) => role === "admin" || role === "sales" || role === "parts";

export interface PartFilters {
  q: string;
  category: string;
  bin: string;
  replaced: boolean;
  /** "", "low", "in" or "out". */
  stock: string;
  ordering: string;
}

export const EMPTY_PART_FILTERS: PartFilters = { q: "", category: "", bin: "", replaced: false, stock: "", ordering: "number" };

export function partParams(f: PartFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (f.q.trim()) params.set("q", f.q.trim());
  if (f.category) params.set("category", f.category);
  if (f.bin) params.set("bin", f.bin);
  if (f.replaced) params.set("replaced", "1");
  if (f.stock) params.set("stock", f.stock);
  if (f.ordering !== "number") params.set("ordering", f.ordering);
  return params;
}

export function useParts(filters: PartFilters, page = 1, pageSize = 50) {
  const q = useDebounced(filters.q);
  const params = partParams({ ...filters, q });
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return useQuery({
    queryKey: partKeys.list(params.toString()),
    queryFn: () => api<Paginated<PartRow>>(`${BASE}?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function usePart(id: string) {
  return useQuery({ queryKey: partKeys.detail(id), queryFn: () => api<Part>(`${BASE}/${id}`), enabled: Boolean(id) });
}

export function usePartFacets() {
  return useQuery({ queryKey: ["parts", "facets"], queryFn: () => api<PartFacets>(`${BASE}/facets`), staleTime: 5 * 60_000 });
}

export function useBins() {
  return useQuery({ queryKey: partKeys.bins, queryFn: () => api<PartBin[]>("/api/v1/bins") });
}

export function useSavePart(id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Part>(id ? `${BASE}/${id}` : BASE, { method: id ? "PATCH" : "POST", body }),
    onSuccess: (part) => {
      qc.setQueryData(partKeys.detail(part.id), part);
      void qc.invalidateQueries({ queryKey: partKeys.all });
    },
  });
}

export function usePartAction(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (what: "remove" | "restore") =>
      api<unknown>(what === "remove" ? `${BASE}/${id}` : `${BASE}/${id}/restore`, { method: what === "remove" ? "DELETE" : "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: partKeys.all }),
  });
}

export function useSaveBin(id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { code: string; description: string }) =>
      api<PartBin>(id ? `/api/v1/bins/${id}` : "/api/v1/bins", { method: id ? "PATCH" : "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: partKeys.bins }),
  });
}

export function useBinAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, restore }: { id: string; restore?: boolean }) =>
      api<unknown>(restore ? `/api/v1/bins/${id}/restore` : `/api/v1/bins/${id}`, { method: restore ? "POST" : "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: partKeys.bins }),
  });
}

export function useNumberCheck(manufacturer: string, number: string, excludeId?: string) {
  const n = useDebounced(number.trim(), 400);
  const m = useDebounced(manufacturer.trim(), 400);
  return useQuery({
    queryKey: ["parts", "number-check", m, n, excludeId],
    queryFn: () =>
      api<{ duplicate: { id: string; label: string; is_deleted: boolean } | null; same_number: { id: string; label: string }[] }>(
        `${BASE}/number-check?manufacturer=${encodeURIComponent(m)}&number=${encodeURIComponent(n)}${excludeId ? `&exclude=${excludeId}` : ""}`,
      ),
    enabled: n.length >= 2,
  });
}

/** "Hyundai 31N4-01050" or just the number. */
export const partLabel = (p: { manufacturer: string; part_number: string }) => [p.manufacturer, p.part_number].filter(Boolean).join(" ");
