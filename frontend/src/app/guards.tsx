import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router";

import { AppShell } from "@/components/shell/AppShell";
import { FullPageError, FullPageLoading } from "@/components/states";
import { useMe } from "@/lib/auth";
import { clearPack } from "@/lib/offline/store";
import type { Role } from "@/lib/types";

/** Signed-in area. Sends visitors to sign in, and admins without 2FA to setup. */
export function RequireAuth() {
  const { data, isPending, isError, refetch } = useMe();
  const location = useLocation();
  const signedOut = data?.authenticated === false;
  useEffect(() => {
    // Nobody signed in (signed out, or the session ended): no saved copy stays behind.
    if (signedOut) void clearPack();
  }, [signedOut]);
  if (isPending) return <FullPageLoading />;
  if (isError) return <FullPageError onRetry={() => void refetch()} />;
  if (!data.authenticated) {
    const next = location.pathname + location.search;
    return <Navigate to={`/login${next !== "/" ? `?next=${encodeURIComponent(next)}` : ""}`} replace />;
  }
  if (data.two_factor.setup_needed) return <Navigate to="/setup-2fa" replace />;
  return <AppShell user={data.user} />;
}

export function RequireRole({ roles }: { roles: Role[] }) {
  const { data } = useMe();
  if (!data?.authenticated) return null;
  if (!roles.includes(data.user.role)) return <Navigate to="/" replace />;
  return <Outlet />;
}

export function useCurrentUser() {
  const { data } = useMe();
  if (!data?.authenticated) throw new Error("useCurrentUser used outside RequireAuth");
  return data.user;
}
