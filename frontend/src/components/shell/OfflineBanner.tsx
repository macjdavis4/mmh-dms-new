import { WifiOff } from "lucide-react";
import { Link } from "react-router";

import { useOfflinePack, useOnline } from "@/lib/offline/sync";

/** Shown while the device has no network: points to the saved copy. */
export function OfflineBanner() {
  const online = useOnline();
  const pack = useOfflinePack();
  if (online) return null;
  return (
    <div role="status" className="bg-warning/15 text-foreground border-warning/40 flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2 text-sm sm:px-8">
      <WifiOff className="text-warning size-4 shrink-0" aria-hidden="true" />
      <span className="font-semibold">You're offline.</span>
      <span>Changes can't be saved until the connection is back.</span>
      {pack.data && (
        <Link to="/offline" className="text-primary font-semibold underline">
          Open the saved copy ({pack.data.units.length} units)
        </Link>
      )}
    </div>
  );
}
