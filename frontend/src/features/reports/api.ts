import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { formatCents, formatDate, formatQty } from "@/lib/format";
import type { DashboardTile, ReportCellKind, ReportData, ReportSummary } from "@/lib/types";

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<{ tiles: DashboardTile[] }>("/api/v1/dashboard"),
    refetchInterval: 5 * 60_000,
  });
}

export function useReports(enabled = true) {
  return useQuery({
    queryKey: ["reports", "list"],
    queryFn: () => api<{ reports: ReportSummary[]; periods: { value: string; label: string }[] }>("/api/v1/reports"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

/** `period=last_month`, or `from` and `to`. */
export interface PeriodChoice {
  period: string;
  from: string;
  to: string;
}

export function periodParams(p: PeriodChoice): URLSearchParams {
  const params = new URLSearchParams();
  if (p.period === "custom") {
    if (p.from) params.set("from", p.from);
    if (p.to) params.set("to", p.to);
  } else if (p.period) {
    params.set("period", p.period);
  }
  return params;
}

export function useReport(key: string, choice: PeriodChoice) {
  const params = periodParams(choice);
  const ready = choice.period !== "custom" || Boolean(choice.from && choice.to);
  return useQuery({
    queryKey: ["reports", key, params.toString()],
    queryFn: () => api<ReportData>(`/api/v1/reports/${key}?${params.toString()}`),
    enabled: ready,
    placeholderData: keepPreviousData,
  });
}

export function csvUrl(key: string, choice: PeriodChoice): string {
  const params = periodParams(choice);
  params.set("download", "csv");
  return `/api/v1/reports/${key}?${params.toString()}`;
}

/** A report cell as people read it. */
export function formatCell(value: string | number | null | undefined, kind: ReportCellKind): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (kind) {
    case "money":
      return formatCents(value);
    case "qty":
      return formatQty(value);
    case "date":
      return formatDate(String(value));
    case "days":
      return `${String(value)} d`;
    case "int":
      return Number(value).toLocaleString("en-US");
    default:
      return String(value);
  }
}

export const isNumeric = (kind: ReportCellKind) => kind !== "text" && kind !== "date";
