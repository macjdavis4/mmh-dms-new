import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { LaborLine, Mechanic, Role, WorkOrder, WorkOrderRow } from "@/lib/types";

const BASE = "/api/v1/work-orders";

export const woKeys = {
  all: ["work-orders"] as const,
  list: (params: string) => ["work-orders", "list", params] as const,
  detail: (id: string) => ["work-orders", "detail", id] as const,
};

// Mirrors apps/service/views.py (the server enforces it).
export const canEditWorkOrders = (role: Role) => role === "admin" || role === "service";

export interface WorkOrderFilters {
  scope: "open" | "completed" | "cancelled" | "all";
  q: string;
  mine: boolean;
  unit?: string;
}

export function useWorkOrders(filters: WorkOrderFilters, page = 1, pageSize = 50) {
  const q = useDebounced(filters.q.trim());
  const params = new URLSearchParams({ scope: filters.scope, page: String(page), page_size: String(pageSize) });
  if (q) params.set("q", q);
  if (filters.mine) params.set("assigned", "me");
  if (filters.unit) params.set("unit", filters.unit);
  return useQuery({
    queryKey: woKeys.list(params.toString()),
    queryFn: () => api<Paginated<WorkOrderRow>>(`${BASE}?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function useWorkOrder(id: string) {
  return useQuery({ queryKey: woKeys.detail(id), queryFn: () => api<WorkOrder>(`${BASE}/${id}`) });
}

export function useWorkOrderCounts(enabled = true) {
  return useQuery({
    queryKey: ["work-orders", "counts"],
    queryFn: () => api<{ open: number; mine: number; on_hold: number }>(`${BASE}/counts`),
    enabled,
  });
}

export function useMechanics() {
  return useQuery({
    queryKey: ["work-orders", "mechanics"],
    queryFn: () => api<Mechanic[]>(`${BASE}/mechanics`),
    staleTime: 5 * 60_000,
  });
}

function useRefresh() {
  const qc = useQueryClient();
  return (wo?: WorkOrder) => {
    if (wo) qc.setQueryData(woKeys.detail(wo.id), wo);
    void qc.invalidateQueries({ queryKey: woKeys.all });
    void qc.invalidateQueries({ queryKey: ["units"] }); // hours and service history
  };
}

export function useSaveWorkOrder(id?: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<WorkOrder>(id ? `${BASE}/${id}` : BASE, { method: id ? "PATCH" : "POST", body }),
    onSuccess: (wo) => refresh(wo),
  });
}

export function useSetStatus(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { status: string; reason?: string }) => api<WorkOrder>(`${BASE}/${id}/status`, { method: "POST", body }),
    onSuccess: (wo) => refresh(wo),
  });
}

export function useAddLabor(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { mechanic: string; work_date: string; hours: string; description: string }) =>
      api<LaborLine>(`${BASE}/${id}/labor`, { method: "POST", body }),
    onSuccess: () => refresh(),
  });
}

export function useLaborAction() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ lineId, restore }: { lineId: string; restore?: boolean }) =>
      restore
        ? api<LaborLine>(`/api/v1/labor/${lineId}/restore`, { method: "POST" })
        : api<null>(`/api/v1/labor/${lineId}`, { method: "DELETE" }),
    onSuccess: () => refresh(),
  });
}
