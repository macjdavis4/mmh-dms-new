import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useDebounced } from "@/hooks/useDebounced";
import { api, type Paginated } from "@/lib/api";
import type { Address, Contact, Customer, CustomerRow } from "@/lib/types";

export const customerKeys = {
  all: ["customers"] as const,
  list: (params: string) => ["customers", "list", params] as const,
  detail: (id: string) => ["customers", "detail", id] as const,
};

export function useCustomers(params: { q: string; kind: string; ordering: string; includeDeleted?: boolean }) {
  const q = useDebounced(params.q);
  const search = new URLSearchParams({ page_size: "100", ordering: params.ordering });
  if (q) search.set("q", q);
  if (params.kind !== "all") search.set("kind", params.kind);
  if (params.includeDeleted) search.set("include_deleted", "1");
  return useQuery({
    queryKey: customerKeys.list(search.toString()),
    queryFn: () => api<Paginated<CustomerRow>>(`/api/v1/customers?${search.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: string) {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: () => api<Customer>(`/api/v1/customers/${id}`),
    enabled: Boolean(id),
  });
}

export type CustomerInput = Pick<Customer, "name" | "kind" | "account_number" | "phone" | "email" | "website" | "notes">;

export function useSaveCustomer(id?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<CustomerInput>) =>
      id
        ? api<Customer>(`/api/v1/customers/${id}`, { method: "PATCH", body })
        : api<Customer>("/api/v1/customers", { method: "POST", body }),
    onSuccess: (saved) => {
      qc.setQueryData(customerKeys.detail(saved.id), saved);
      void qc.invalidateQueries({ queryKey: customerKeys.all });
    },
  });
}

export function useRemoveCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, restore }: { id: string; restore?: boolean }) =>
      restore
        ? api<Customer>(`/api/v1/customers/${id}/restore`, { method: "POST" })
        : api<undefined>(`/api/v1/customers/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: customerKeys.all }),
  });
}

/** Contacts and addresses share one shape of API. */
export function useSaveChild<T extends Contact | Address>(kind: "contacts" | "addresses", customerId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Partial<T> }) =>
      id
        ? api<T>(`/api/v1/${kind}/${id}`, { method: "PATCH", body })
        : api<T>(`/api/v1/${kind}`, { method: "POST", body: { ...body, customer: customerId } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: customerKeys.all }),
  });
}

export function useRemoveChild(kind: "contacts" | "addresses") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, restore }: { id: string; restore?: boolean }) =>
      restore
        ? api(`/api/v1/${kind}/${id}/restore`, { method: "POST" })
        : api<undefined>(`/api/v1/${kind}/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: customerKeys.all }),
  });
}
