import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { MaintenancePlan, PlanStatus, WorkOrder } from "@/lib/types";

const BASE = "/api/v1/maintenance-plans";

export const planKeys = {
  all: ["maintenance-plans"] as const,
  unit: (unitId: string) => ["maintenance-plans", "unit", unitId] as const,
  due: (all: boolean) => ["maintenance-plans", "due", all] as const,
};

export function useUnitPlans(unitId: string, enabled = true) {
  return useQuery({
    queryKey: planKeys.unit(unitId),
    queryFn: () => api<MaintenancePlan[]>(`${BASE}?unit=${unitId}`),
    enabled,
  });
}

export function useDuePlans(all = false, enabled = true) {
  return useQuery({
    queryKey: planKeys.due(all),
    queryFn: () =>
      api<{ counts: { overdue: number; due_soon: number }; results: MaintenancePlan[] }>(`${BASE}/due${all ? "?all=1" : ""}`),
    enabled,
  });
}

function useRefresh() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: planKeys.all });
    void qc.invalidateQueries({ queryKey: ["work-orders"] });
  };
}

export function useSavePlan(id?: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<MaintenancePlan>(id ? `${BASE}/${id}` : BASE, { method: id ? "PATCH" : "POST", body }),
    onSuccess: refresh,
  });
}

export function usePlanRemove() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, restore }: { id: string; restore?: boolean }) =>
      restore ? api<MaintenancePlan>(`${BASE}/${id}/restore`, { method: "POST" }) : api<null>(`${BASE}/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
}

export function usePlanWorkOrder() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (planId: string) => api<WorkOrder>(`${BASE}/${planId}/work-order`, { method: "POST" }),
    onSuccess: refresh,
  });
}

const plural = (n: number, one: string) => `${formatNumber(n)} ${n === 1 ? one : `${one}s`}`;

/** "Overdue by 70 h", "Due in 20 days", "Next: Jan 3, 2027 or 9,370 h", "Paused". */
export function dueWords(st: PlanStatus | null): string {
  if (!st) return "";
  if (st.state === "paused") return "Paused";
  const days = st.days_left;
  const hours = st.hours_left === null ? null : Number(st.hours_left);
  if (st.state === "overdue") {
    if (hours !== null && hours <= 0) return `Overdue by ${formatNumber(Math.abs(hours))} h`;
    if (days !== null) return days === -1 ? "Overdue by 1 day" : `Overdue by ${plural(-days, "day")}`;
  }
  if (st.state === "due_soon") {
    const parts = [];
    if (days !== null && days <= 30) parts.push(days === 0 ? "today" : `in ${plural(days, "day")}`);
    if (hours !== null && hours <= 50) parts.push(`in ${formatNumber(hours)} h`);
    return `Due ${parts.join(" or ")}`;
  }
  const next = [st.next_due_on ? formatDate(st.next_due_on) : null, st.next_due_hours ? `${formatNumber(st.next_due_hours)} h` : null].filter(Boolean);
  return next.length ? `Next: ${next.join(" or ")}` : "";
}

export function intervalWords(plan: Pick<MaintenancePlan, "interval_hours" | "interval_days">): string {
  const parts = [];
  if (plan.interval_hours) parts.push(`${formatNumber(plan.interval_hours)} hours`);
  if (plan.interval_days) {
    const d = plan.interval_days;
    parts.push(d % 365 === 0 ? plural(d / 365, "year") : d % 30 === 0 ? plural(d / 30, "month") : plural(d, "day"));
  }
  return `Every ${parts.join(" or ")}`;
}
