import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { partKeys } from "@/features/parts/api";
import { stockKeys } from "@/features/parts/stock";
import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { BackorderLine, Invoice, InvoiceRow, Role } from "@/lib/types";
import { uploadForm } from "@/lib/upload";

const BASE = "/api/v1/parts-invoices";

// Mirrors apps/parts/invoice_api.py (the server enforces it). Invoices show
// our cost, so only cost roles see them.
export const canSeeInvoices = (role: Role) => role === "admin" || role === "parts" || role === "sales";
export const canReceiveInvoices = (role: Role) => role === "admin" || role === "parts";

export const invoiceKeys = {
  all: ["parts-invoices"] as const,
  list: (params: string) => ["parts-invoices", "list", params] as const,
  detail: (id: string) => ["parts-invoices", "detail", id] as const,
  backorders: ["parts-invoices", "backorders"] as const,
  counts: ["parts-invoices", "counts"] as const,
};

export const fileUrl = (id: string) => `${BASE}/${id}/file`;

export function useInvoices(status: string, q: string, page = 1, pageSize = 50) {
  const query = useDebounced(q);
  const params = new URLSearchParams({ status, page: String(page), page_size: String(pageSize) });
  if (query.trim()) params.set("q", query.trim());
  return useQuery({
    queryKey: invoiceKeys.list(params.toString()),
    queryFn: () => api<Paginated<InvoiceRow>>(`${BASE}?${params.toString()}`),
    placeholderData: keepPreviousData,
    // Keep checking while an upload is being read.
    refetchInterval: (query) => (query.state.data?.results.some((r) => r.status === "reading") ? 2000 : false),
  });
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: invoiceKeys.detail(id),
    queryFn: () => api<Invoice>(`${BASE}/${id}`),
    refetchInterval: (query) => (query.state.data?.status === "reading" ? 2000 : false),
  });
}

export function useInvoiceCounts(enabled = true) {
  return useQuery({
    queryKey: invoiceKeys.counts,
    queryFn: () => api<{ to_check: number; partial: number; backorder_lines: number }>(`${BASE}/counts`),
    enabled,
  });
}

export function useBackorders() {
  return useQuery({ queryKey: invoiceKeys.backorders, queryFn: () => api<BackorderLine[]>(`${BASE}/backorders`) });
}

function useRefresh() {
  const qc = useQueryClient();
  return (invoice?: Invoice) => {
    if (invoice) qc.setQueryData(invoiceKeys.detail(invoice.id), invoice);
    void qc.invalidateQueries({ queryKey: invoiceKeys.all });
    void qc.invalidateQueries({ queryKey: partKeys.all });
    void qc.invalidateQueries({ queryKey: stockKeys.all });
  };
}

export function useUploadInvoice() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ file, onProgress }: { file: File; onProgress?: (f: number) => void }) => uploadForm<Invoice>(BASE, { file }, onProgress),
    onSuccess: (invoice) => refresh(invoice),
  });
}

export function useCreateBlankInvoice() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: () => api<Invoice>(BASE, { method: "POST", body: {} }),
    onSuccess: (invoice) => refresh(invoice),
  });
}

export function useSaveInvoice(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Invoice>(`${BASE}/${id}`, { method: "PATCH", body }),
    onSuccess: (invoice) => refresh(invoice),
  });
}

export type InvoiceAction =
  | { kind: "receive"; lines: { line: string; quantity: string }[]; update_costs: boolean }
  | { kind: "read-again" }
  | { kind: "cancel"; reason: string };

export function useInvoiceAction(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (action: InvoiceAction) => {
      const { kind, ...body } = action;
      return api<Invoice>(`${BASE}/${id}/${kind}`, { method: "POST", body });
    },
    onSuccess: (invoice) => refresh(invoice),
  });
}

export function useLineAction() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, kind, reason }: { id: string; kind: "close" | "reopen"; reason?: string }) =>
      api<unknown>(`/api/v1/parts-invoice-lines/${id}/${kind}`, { method: "POST", body: kind === "close" ? { reason: reason ?? "" } : {} }),
    onSuccess: () => refresh(),
  });
}
