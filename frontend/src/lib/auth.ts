import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { clearPack } from "@/lib/offline/store";
import { api } from "./api";
import type { Me, SystemStatus } from "./types";

export const meKey = ["auth", "me"] as const;

export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: () => api<Me>("/api/v1/auth/me"),
    staleTime: 60_000,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => api<SystemStatus>("/api/v1/system/status"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export type LoginResult = { status: "otp_required" } | ({ status: "ok" } & Me);

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { email: string; password: string }) =>
      api<LoginResult>("/api/v1/auth/login", { method: "POST", body: vars }),
    onSuccess: (data) => {
      if (data.status === "ok") {
        const { status: _status, ...me } = data;
        qc.setQueryData(meKey, me);
      }
    },
  });
}

export function useVerifyCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api<{ status: "ok" } & Me>("/api/v1/auth/login/verify", { method: "POST", body: { code } }),
    onSuccess: (data) => {
      const { status: _status, ...me } = data;
      qc.setQueryData(meKey, me);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    // The device's offline copy goes first, even if the server can't be reached.
    mutationFn: async () => {
      await clearPack();
      return api<undefined>("/api/v1/auth/logout", { method: "POST" });
    },
    onSettled: () => {
      qc.clear();
      qc.setQueryData(meKey, { authenticated: false });
    },
  });
}
