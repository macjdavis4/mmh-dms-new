import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { Quote, QuoteRow, Role } from "@/lib/types";

const BASE = "/api/v1/quotes";

export const quoteKeys = {
  all: ["quotes"] as const,
  list: (params: string) => ["quotes", "list", params] as const,
  detail: (id: string) => ["quotes", "detail", id] as const,
};

// Mirrors apps/sales/views.py (the server enforces it).
export const canSell = (role: Role) => role === "admin" || role === "sales";
export const canVoidSales = (role: Role) => role === "admin";

export interface QuoteFilters {
  scope: "open" | "sold" | "closed" | "all";
  q: string;
  mine: boolean;
}

export function useQuotes(filters: QuoteFilters, page = 1, pageSize = 50) {
  const q = useDebounced(filters.q.trim());
  const params = new URLSearchParams({ scope: filters.scope, page: String(page), page_size: String(pageSize) });
  if (q) params.set("q", q);
  if (filters.mine) params.set("mine", "1");
  return useQuery({
    queryKey: quoteKeys.list(params.toString()),
    queryFn: () => api<Paginated<QuoteRow>>(`${BASE}?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function useQuote(id: string) {
  return useQuery({ queryKey: quoteKeys.detail(id), queryFn: () => api<Quote>(`${BASE}/${id}`), enabled: Boolean(id) });
}

function useRefresh() {
  const qc = useQueryClient();
  return (quote?: Quote) => {
    if (quote) qc.setQueryData(quoteKeys.detail(quote.id), quote);
    void qc.invalidateQueries({ queryKey: quoteKeys.all });
  };
}

export function useSaveQuote(id?: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Quote>(id ? `${BASE}/${id}` : BASE, { method: id ? "PATCH" : "POST", body }),
    onSuccess: (quote) => refresh(quote),
  });
}

export function useQuoteStatus(id: string) {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (status: string) => api<Quote>(`${BASE}/${id}/status`, { method: "POST", body: { status } }),
    onSuccess: (quote) => refresh(quote),
  });
}

export function useSaleCheck(id: string, enabled: boolean) {
  return useQuery({
    queryKey: [...quoteKeys.detail(id), "sell-check"],
    queryFn: () => api<{ problems: Record<string, string[]> }>(`${BASE}/${id}/sell`),
    enabled,
    staleTime: 0,
  });
}

/** Recording the sale changes owners, stock status and prices on units too. */
export function useRecordSale(id: string) {
  const qc = useQueryClient();
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: { sale_date: string; invoice_number: string; hours: Record<string, string> }) =>
      api<Quote & { warnings: string[] }>(`${BASE}/${id}/sell`, { method: "POST", body }),
    onSuccess: (quote) => {
      refresh(quote);
      void qc.invalidateQueries({ queryKey: ["units"] });
      void qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useVoidSale(quoteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ saleId, reason }: { saleId: string; reason: string }) =>
      api<unknown>(`/api/v1/sales/${saleId}/void`, { method: "POST", body: { reason } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: quoteKeys.detail(quoteId) });
      void qc.invalidateQueries({ queryKey: quoteKeys.all });
      void qc.invalidateQueries({ queryKey: ["units"] });
    },
  });
}
