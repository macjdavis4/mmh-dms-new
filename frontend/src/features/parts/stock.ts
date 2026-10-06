import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { woKeys } from "@/features/service/api";
import { api, type Paginated } from "@/lib/api";
import type { PartRow, Role, StockCheck, StockMovement } from "@/lib/types";

import { partKeys } from "./api";

const BASE = "/api/v1/stock-movements";

// Mirrors apps/parts/views.py (the server enforces it).
/** Receive, count and reverse. */
export const canKeepStock = (role: Role) => role === "admin" || role === "parts";
/** Put parts on a work order and take them back off. */
export const canUseParts = (role: Role) => role === "admin" || role === "parts" || role === "service";
/** Run the ledger check on demand. */
export const canRunStockCheck = (role: Role) => role === "admin";

export const stockKeys = {
  all: ["stock"] as const,
  movements: (params: string) => ["stock", "movements", params] as const,
  low: ["stock", "low"] as const,
  check: ["stock", "check"] as const,
};

export function useStockMovements(filter: { part?: string; work_order?: string }, page = 1, pageSize = 25) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (filter.part) params.set("part", filter.part);
  if (filter.work_order) params.set("work_order", filter.work_order);
  return useQuery({
    queryKey: stockKeys.movements(params.toString()),
    queryFn: () => api<Paginated<StockMovement>>(`${BASE}?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function useLowStock() {
  return useQuery({
    queryKey: stockKeys.low,
    queryFn: () => api<{ results: PartRow[]; last_check: StockCheck | null }>("/api/v1/parts/low-stock"),
  });
}

export function useRunStockCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<StockCheck>(`${BASE}/check`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: stockKeys.all }),
  });
}

export type StockAction =
  | { kind: "receive"; part: string; quantity: string; unit_cost?: string; reference?: string; note?: string }
  | { kind: "count"; part: string; counted: string; note?: string }
  | { kind: "issue" | "return"; part: string; work_order: string; quantity: string; note?: string }
  | { kind: "reverse"; id: string; note?: string };

/** Every stock change; refreshes the part, the lists and the work order. */
export function useStockAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: StockAction) => {
      if (action.kind === "reverse") {
        return api<StockMovement>(`${BASE}/${action.id}/reverse`, { method: "POST", body: { note: action.note ?? "" } });
      }
      const { kind, ...body } = action;
      return api<StockMovement>(`${BASE}/${kind}`, { method: "POST", body });
    },
    onSuccess: (movement) => {
      void qc.invalidateQueries({ queryKey: stockKeys.all });
      void qc.invalidateQueries({ queryKey: partKeys.all });
      if (movement.work_order) void qc.invalidateQueries({ queryKey: woKeys.detail(movement.work_order) });
    },
  });
}

/** "+12", "-3" for the history list. */
export function signed(quantity: string): string {
  const n = Number(quantity);
  const text = Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
  return n > 0 ? `+${text}` : `−${text}`;
}
