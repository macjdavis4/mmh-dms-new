import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import { uploadForm } from "@/lib/upload";
import type {
  AuditEntry,
  HourReading,
  OwnershipRecord,
  Unit,
  UnitChange,
  UnitChangeTotals,
  UnitFacets,
  UnitFile,
  UnitRow,
} from "@/lib/types";

export const unitKeys = {
  all: ["units"] as const,
  list: (params: string) => ["units", "list", params] as const,
  detail: (id: string) => ["units", "detail", id] as const,
  sub: (id: string, what: string) => ["units", "detail", id, what] as const,
};

export interface UnitFilters {
  scope: "stock" | "all" | "customer";
  q: string;
  condition: string;
  make: string;
  model: string;
  fuel_type: string;
  status: string;
  capacity_min: string;
  capacity_max: string;
  lift_min: string;
  lift_max: string;
  price_min: string;
  price_max: string;
  needs_review: boolean;
  ordering: string;
}

export const EMPTY_FILTERS: UnitFilters = {
  scope: "stock",
  q: "",
  condition: "",
  make: "",
  model: "",
  fuel_type: "",
  status: "",
  capacity_min: "",
  capacity_max: "",
  lift_min: "",
  lift_max: "",
  price_min: "",
  price_max: "",
  needs_review: false,
  ordering: "make",
};

export function filtersToParams(filters: UnitFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (key === "needs_review") {
      if (value) params.set(key, "1");
    } else if (typeof value === "string" && value !== "" && !(key === "scope" && value === "stock") && !(key === "ordering" && value === "make")) {
      params.set(key, value);
    }
  }
  return params;
}

export function paramsToFilters(params: URLSearchParams): UnitFilters {
  const f: UnitFilters = { ...EMPTY_FILTERS };
  for (const key of Object.keys(EMPTY_FILTERS) as (keyof UnitFilters)[]) {
    const value = params.get(key);
    if (value === null) continue;
    if (key === "needs_review") f.needs_review = value === "1";
    else (f as unknown as Record<string, string>)[key] = value;
  }
  return f;
}

export function useUnits(filters: UnitFilters, page = 1, pageSize = 48) {
  const q = useDebounced(filters.q);
  const params = filtersToParams({ ...filters, q });
  if (!params.has("scope")) params.set("scope", filters.scope);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return useQuery({
    queryKey: unitKeys.list(params.toString()),
    queryFn: () => api<Paginated<UnitRow>>(`/api/v1/units?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function useCustomerUnits(customerId: string) {
  return useQuery({
    queryKey: unitKeys.list(`owner=${customerId}`),
    queryFn: () => api<Paginated<UnitRow>>(`/api/v1/units?scope=all&owner=${customerId}&page_size=200`),
  });
}

export function useFormerUnits(customerId: string) {
  return useQuery({
    queryKey: unitKeys.list(`former_owner=${customerId}`),
    queryFn: () => api<Paginated<UnitRow>>(`/api/v1/units?scope=all&former_owner=${customerId}&page_size=200`),
  });
}

export interface ChangeFilters {
  direction: "" | "out" | "in" | "between";
  reason: string;
  date_from: string;
  date_to: string;
  q: string;
}

export const EMPTY_CHANGE_FILTERS: ChangeFilters = { direction: "", reason: "", date_from: "", date_to: "", q: "" };

export function changeParams(filters: ChangeFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters) as [string, string][]) if (value) params.set(key, value);
  return params;
}

/** "Bought and sold": every change of hands, newest first. */
export function useUnitChanges(filters: ChangeFilters, page: number, pageSize: number) {
  const q = useDebounced(filters.q);
  const params = changeParams({ ...filters, q });
  const totalsKey = params.toString();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const list = useQuery({
    queryKey: ["units", "changes", params.toString()],
    queryFn: () => api<Paginated<UnitChange>>(`/api/v1/unit-changes?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
  const totals = useQuery({
    queryKey: ["units", "changes", "totals", totalsKey],
    queryFn: () => api<UnitChangeTotals>(`/api/v1/unit-changes/totals?${totalsKey}`),
    placeholderData: keepPreviousData,
  });
  return { list, totals };
}

export function useFacets() {
  return useQuery({
    queryKey: ["units", "facets"],
    queryFn: () => api<UnitFacets>("/api/v1/units/facets"),
    staleTime: 5 * 60_000,
  });
}

export function useUnit(id: string) {
  return useQuery({
    queryKey: unitKeys.detail(id),
    queryFn: () => api<Unit>(`/api/v1/units/${id}`),
    enabled: Boolean(id),
  });
}

export function useUnitSub<T>(id: string, what: "hours" | "ownership" | "files" | "history") {
  return useQuery({
    queryKey: unitKeys.sub(id, what),
    queryFn: () => api<T>(`/api/v1/units/${id}/${what}`),
  });
}

export const useHours = (id: string) => useUnitSub<HourReading[]>(id, "hours");
export const useOwnership = (id: string) => useUnitSub<OwnershipRecord[]>(id, "ownership");
export const useFiles = (id: string) => useUnitSub<UnitFile[]>(id, "files");
export const useHistory = (id: string) => useUnitSub<AuditEntry[]>(id, "history");

export function useSaveUnit(id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      id
        ? api<Unit>(`/api/v1/units/${id}`, { method: "PATCH", body })
        : api<Unit>("/api/v1/units", { method: "POST", body }),
    onSuccess: (unit) => {
      qc.setQueryData(unitKeys.detail(unit.id), unit);
      void qc.invalidateQueries({ queryKey: unitKeys.all });
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useUnitAction<TBody, TResult = unknown>(id: string, path: string, method: "POST" | "DELETE" = "POST") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) => api<TResult>(`/api/v1/${path}`, { method, body: method === "DELETE" ? undefined : body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: unitKeys.detail(id) });
      void qc.invalidateQueries({ queryKey: unitKeys.all });
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

/** Correct a recorded change of hands (reason, price, cost, reference, note). */
export function useEditDeal(unitId: string, recordId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<OwnershipRecord>(`/api/v1/ownership-records/${recordId}`, { method: "PATCH", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: unitKeys.detail(unitId) });
      void qc.invalidateQueries({ queryKey: unitKeys.all });
    },
  });
}

export function useSerialCheck(serial: string, excludeId?: string) {
  const s = useDebounced(serial.trim(), 400);
  return useQuery({
    queryKey: ["units", "serial-check", s, excludeId],
    queryFn: () =>
      api<{ duplicates: { id: string; label: string; is_deleted: boolean }[] }>(
        `/api/v1/units/serial-check?serial=${encodeURIComponent(s)}${excludeId ? `&exclude=${excludeId}` : ""}`,
      ),
    enabled: s.length >= 3,
  });
}

/** Multipart upload with progress (fetch can't report upload progress). */
export function uploadUnitFile(
  unitId: string,
  file: File,
  kind: UnitFile["kind"],
  onProgress: (fraction: number) => void,
): Promise<UnitFile> {
  return uploadForm<UnitFile>(`/api/v1/units/${unitId}/files`, { file, kind }, onProgress);
}

export function useUploadInvalidation(unitId: string) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: unitKeys.detail(unitId) });
    void qc.invalidateQueries({ queryKey: unitKeys.all });
  };
}
