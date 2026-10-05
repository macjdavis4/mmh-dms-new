import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Paginated } from "@/lib/api";
import type { ApiKey, ImportBatch, ImportBatchRow, ImportFile, ImportRow, ImportStatus } from "@/lib/types";
import { uploadForm } from "@/lib/upload";

const BASE = "/api/v1/imports/batches";

export const importKeys = {
  all: ["imports"] as const,
  list: (page: number) => ["imports", "list", page] as const,
  detail: (id: string) => ["imports", "detail", id] as const,
  rows: (id: string, show: string, q: string, page: number) => ["imports", "detail", id, "rows", show, q, page] as const,
};

/** Statuses where the server is still working, so the page keeps checking. */
export const BUSY: ImportStatus[] = ["queued", "importing", "undoing"];

export const TEMPLATE_URL = `${BASE}/template.csv`;
export const SAMPLE_URL = `${BASE}/sample.csv`;

export function useBatches(page = 1) {
  return useQuery({
    queryKey: importKeys.list(page),
    queryFn: () => api<Paginated<ImportBatchRow>>(`${BASE}?page=${page}`),
    placeholderData: keepPreviousData,
  });
}

export function useBatch(id: string) {
  return useQuery({
    queryKey: importKeys.detail(id),
    queryFn: () => api<ImportBatch>(`${BASE}/${id}`),
    refetchInterval: (query) => (query.state.data && BUSY.includes(query.state.data.status) ? 2000 : false),
  });
}

export const ROW_PAGE_SIZE = 50;

export function useBatchRows(id: string, show: string, q: string, page: number, status: ImportStatus | undefined) {
  const params = new URLSearchParams({ page: String(page), page_size: String(ROW_PAGE_SIZE) });
  if (show) params.set("show", show);
  if (q) params.set("q", q);
  return useQuery({
    // The status is part of the key so results refresh when an import finishes.
    queryKey: [...importKeys.rows(id, show, q, page), status],
    queryFn: () => api<Paginated<ImportRow>>(`${BASE}/${id}/rows?${params.toString()}`),
    placeholderData: keepPreviousData,
  });
}

export function createBatch(file: File, onProgress: (f: number) => void): Promise<ImportBatch> {
  return uploadForm<ImportBatch>(BASE, { file }, onProgress);
}

export function uploadScan(batchId: string, file: File, onProgress: (f: number) => void): Promise<ImportFile> {
  return uploadForm<ImportFile>(`${BASE}/${batchId}/files`, { file }, onProgress);
}

type BatchAction = "validate" | "apply" | "undo" | "discard";

export function useBatchAction(id: string, action: BatchAction) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown> = {}) => api<ImportBatch>(`${BASE}/${id}/${action}`, { method: "POST", body }),
    onSuccess: (batch) => {
      qc.setQueryData(importKeys.detail(id), batch);
      void qc.invalidateQueries({ queryKey: importKeys.all });
      if (action === "apply" || action === "undo") {
        void qc.invalidateQueries({ queryKey: ["units"] });
        void qc.invalidateQueries({ queryKey: ["customers"] });
      }
    },
  });
}

// --- API keys (admin) ------------------------------------------------------------------------

const KEYS = "/api/v1/admin/api-keys";

export function useApiKeys() {
  return useQuery({ queryKey: ["api-keys"], queryFn: () => api<ApiKey[]>(KEYS) });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api<ApiKey>(KEYS, { method: "POST", body: { name } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}

export function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<ApiKey>(`${KEYS}/${id}/revoke`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });
}
