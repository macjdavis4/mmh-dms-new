import { AlertTriangle, Info, Lock, OctagonAlert } from "lucide-react";

import { useSystemStatus } from "@/lib/auth";
import { cn } from "@/lib/utils";

const STYLES = {
  info: "bg-primary text-primary-foreground",
  warning: "bg-cta text-cta-foreground",
  critical: "bg-destructive text-destructive-foreground",
} as const;

const ICONS = { info: Info, warning: AlertTriangle, critical: OctagonAlert } as const;

/** Maintenance banner and read-only notice, set by an admin in Site settings. */
export function SystemBanner() {
  const { data } = useSystemStatus();
  if (!data || (!data.banner_message && !data.read_only_mode)) return null;
  const level = data.banner_level;
  const Icon = ICONS[level];
  return (
    <div role="status" aria-live="polite" className="flex flex-col">
      {data.banner_message && (
        <div className={cn("flex items-center gap-2 px-4 py-2.5 text-sm font-semibold", STYLES[level])}>
          <Icon className="size-4 shrink-0" aria-hidden="true" />
          <span>{data.banner_message}</span>
        </div>
      )}
      {data.read_only_mode && (
        <div className="bg-foreground text-background flex items-center gap-2 px-4 py-2 text-sm font-semibold">
          <Lock className="size-4 shrink-0" aria-hidden="true" />
          <span>Read-only mode: you can look things up, but changes are paused.</span>
        </div>
      )}
    </div>
  );
}

export function EnvironmentTag() {
  const { data } = useSystemStatus();
  if (!data || data.environment === "production") return null;
  return (
    <span className="border-cta text-foreground hidden rounded-md border-2 border-dashed px-2 py-0.5 text-[11px] font-bold tracking-widest uppercase sm:inline">
      {data.environment}
    </span>
  );
}
