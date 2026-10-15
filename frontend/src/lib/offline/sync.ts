import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";

import { api, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";
import { isOn, useFlags } from "@/lib/flags";

import type { OfflineUnit, OfflinePack } from "./pack";
import { clearPack, loadPack, savePack } from "./store";

const EVERY = 30 * 60_000;
export const packKey = ["offline-pack"] as const;

interface ServerPack {
  generated_at: string;
  user_id: string;
  keep_days: number;
  units: OfflineUnit[];
}

/** The saved copy, but only for the person signed in on this device. The
 * offline pages work without signing in (that's their point), so when there
 * *is* a connection we ask the server who is signed in, and wipe the copy if
 * nobody is, or someone else is. With no connection the copy is shown as is
 * (it still expires after its keep period). */
async function loadPackForSignedInUser(): Promise<OfflinePack | null> {
  const pack = await loadPack();
  if (!pack || !navigator.onLine) return pack;
  let me: Me;
  try {
    me = await api<Me>("/api/v1/auth/me");
  } catch {
    return pack; // the server can't be reached: that's when the copy is needed
  }
  if (!me.authenticated || me.user.id !== pack.userId) {
    await clearPack();
    return null;
  }
  return pack;
}

/** What's saved on this device (for the offline pages and the account menu). */
export function useOfflinePack() {
  return useQuery({ queryKey: packKey, queryFn: loadPackForSignedInUser, staleTime: 60_000, retry: false });
}

/** Keep this device's copy fresh while signed in and online (every 30 minutes),
 * for this person only; wipe it if the feature is switched off. */
export function useOfflineSync(userId: string) {
  const flags = useFlags();
  const qc = useQueryClient();
  useEffect(() => {
    if (!flags.data) return;
    const on = isOn(flags.data.flags, "offline") && isOn(flags.data.flags, "customers-units");
    let cancelled = false;
    const sync = async () => {
      if (!on) {
        await clearPack();
        void qc.invalidateQueries({ queryKey: packKey });
        return;
      }
      if (!navigator.onLine) return;
      const existing = await loadPack();
      if (existing && existing.userId !== userId) await clearPack();
      try {
        const pack = await api<ServerPack>("/api/v1/offline/units");
        if (cancelled || pack.user_id !== userId) return;
        await savePack({
          userId: pack.user_id,
          generatedAt: pack.generated_at,
          savedAt: new Date().toISOString(),
          keepDays: pack.keep_days,
          units: pack.units,
        });
        void qc.invalidateQueries({ queryKey: packKey });
      } catch (error) {
        // Signed out, or no longer allowed to have a copy: wipe it now.
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          await clearPack();
          void qc.invalidateQueries({ queryKey: packKey });
        }
        // Otherwise offline or the server is busy: keep the copy we have and try later.
      }
    };
    void sync();
    const timer = window.setInterval(() => void sync(), EVERY);
    const onOnline = () => void sync();
    window.addEventListener("online", onOnline);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("online", onOnline);
    };
  }, [flags.data, userId, qc]);
}

function subscribe(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/** False when the device says it has no network. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
}
