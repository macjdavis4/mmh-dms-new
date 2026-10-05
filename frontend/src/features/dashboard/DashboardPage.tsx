import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ClipboardPlus,
  Database,
  FileUp,
  HardDriveDownload,
  PackageCheck,
  Truck,
  Wrench,
} from "lucide-react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { canEditUnits } from "@/features/units/permissions";
import { api, type Paginated } from "@/lib/api";
import { isOn, useFlags } from "@/lib/flags";
import type { AdminHealth, UnitRow } from "@/lib/types";
import { cn } from "@/lib/utils";

function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

type Tile = { label: string; icon: typeof Truck; phase: number; to?: string; count?: number | undefined };

const TILES: Tile[] = [
  { label: "Open work orders", icon: Wrench, phase: 4 },
  { label: "PM due in 30 days", icon: Activity, phase: 5 },
  { label: "Low-stock parts", icon: PackageCheck, phase: 10 },
];

type QuickAction = { label: string; icon: typeof Truck; to: string; phase?: number; hint?: string };

const QUICK_ACTIONS: QuickAction[] = [
  { label: "New work order", icon: ClipboardPlus, to: "/service", phase: 4 },
  { label: "Receive a parts invoice", icon: PackageCheck, to: "/parts", phase: 11 },
];

function StatusRow({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2.5">
      <span className="flex items-center gap-2 text-sm font-medium">
        {ok ? (
          <CheckCircle2 className="text-success size-[18px]" aria-hidden="true" />
        ) : (
          <CircleAlert className="text-destructive size-[18px]" aria-hidden="true" />
        )}
        {label}
      </span>
      <span className={cn("text-sm", ok ? "text-muted-foreground" : "text-destructive font-semibold")}>{detail}</span>
    </li>
  );
}

function SystemHealthCard() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin", "health"],
    queryFn: () => api<AdminHealth>("/api/v1/admin/health"),
    refetchInterval: 60_000,
  });
  const backup = data?.last_backup;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Database className="size-5" aria-hidden="true" /> System health
        </CardTitle>
        <CardDescription>Only admins see this.</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        ) : isError ? (
          <p className="text-destructive text-sm font-semibold">Couldn't check system health.</p>
        ) : (
          <ul className="divide-y">
            <StatusRow ok={data.database === "ok"} label="Database" detail={data.database === "ok" ? "Connected" : data.database} />
            <StatusRow
              ok={data.migrations === "ok"}
              label="Database schema"
              detail={data.migrations === "ok" ? "Up to date" : data.migrations}
            />
            <StatusRow
              ok={(data.jobs.failed ?? 0) === 0}
              label="Background jobs"
              detail={(data.jobs.failed ?? 0) > 0 ? `${data.jobs.failed ?? 0} failed` : `${data.jobs.todo ?? 0} waiting`}
            />
            <StatusRow
              ok={backup?.status === "succeeded"}
              label="Last backup"
              detail={
                backup
                  ? `${backup.status === "succeeded" ? "OK" : backup.status} · ${new Date(backup.started_at).toLocaleString()}`
                  : "None yet"
              }
            />
          </ul>
        )}
        {data && (
          <p className="text-muted-foreground mt-3 flex items-center gap-1.5 text-xs">
            <HardDriveDownload className="size-3.5" aria-hidden="true" /> Version {data.version} · {data.environment}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function useStockCount(enabled: boolean) {
  return useQuery({
    queryKey: ["units", "dashboard-count"],
    queryFn: () => api<Paginated<UnitRow>>("/api/v1/units?scope=stock&page_size=1"),
    enabled,
    select: (d) => d.count,
  });
}

export function DashboardPage() {
  const user = useCurrentUser();
  const flags = useFlags();
  const unitsOn = isOn(flags.data?.flags, "customers-units");
  const stock = useStockCount(unitsOn);
  const tiles: Tile[] = unitsOn
    ? [{ label: "Units in stock", icon: Truck, phase: 2, to: "/units", count: stock.data }, ...TILES]
    : [{ label: "Units in stock", icon: Truck, phase: 2 }, ...TILES];
  const actions: QuickAction[] = [...QUICK_ACTIONS];
  if (isOn(flags.data?.flags, "batch-import") && ["admin", "sales", "service"].includes(user.role)) {
    actions.push({ label: "Import unit cards", icon: FileUp, to: "/imports/new", hint: "Upload a spreadsheet of cards" });
  }
  if (unitsOn) {
    actions.splice(
      1,
      0,
      canEditUnits(user.role)
        ? { label: "Add a unit", icon: Truck, to: "/units/new", hint: "Enter a unit card" }
        : { label: "Browse stock", icon: Truck, to: "/units", hint: "See units for sale" },
    );
  }
  return (
    <div className="flex flex-col gap-8">
      <div>
        <p className="text-muted-foreground text-sm font-medium">
          {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </p>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight sm:text-3xl">
          {greeting()}, {user.first_name || user.email.split("@")[0]}
        </h1>
      </div>

      <section aria-labelledby="tiles-heading">
        <h2 id="tiles-heading" className="sr-only">
          At a glance
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          {tiles.map((tile) => {
            const live = tile.to !== undefined;
            const body = (
              <Card className={cn("h-full gap-3 py-5", live && "hover:border-primary/40 transition-colors")}>
                <CardContent className="flex flex-col gap-3 px-5">
                  <div className="flex items-center justify-between">
                    <span className="bg-primary/10 text-primary grid size-10 place-items-center rounded-xl dark:bg-primary/15">
                      <tile.icon className="size-5" aria-hidden="true" />
                    </span>
                    {!live && (
                      <Badge variant="outline" className="text-muted-foreground font-medium">
                        Phase {tile.phase}
                      </Badge>
                    )}
                  </div>
                  <div>
                    {live && tile.count === undefined ? (
                      <Skeleton className="h-9 w-16" />
                    ) : (
                      <p className={cn("text-3xl font-extrabold", !live && "text-muted-foreground")}>
                        {live ? tile.count : "—"}
                      </p>
                    )}
                    <p className="text-sm font-semibold">{tile.label}</p>
                  </div>
                </CardContent>
              </Card>
            );
            return tile.to ? (
              <Link
                key={tile.label}
                to={tile.to}
                className="focus-visible:ring-ring rounded-xl focus-visible:ring-2 focus-visible:outline-none"
              >
                {body}
              </Link>
            ) : (
              <div key={tile.label}>{body}</div>
            );
          })}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <section aria-labelledby="actions-heading" className="lg:col-span-3">
          <Card className="h-full">
            <CardHeader>
              <CardTitle id="actions-heading" className="text-lg">
                Quick actions
              </CardTitle>
              <CardDescription>These turn on as each part of the system is finished.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {actions.map((action) => (
                <Link
                  key={action.label}
                  to={action.to}
                  className="group hover:border-primary/40 hover:bg-muted/60 focus-visible:ring-ring flex min-h-16 items-center gap-3 rounded-xl border p-4 transition-colors focus-visible:ring-2 focus-visible:outline-none"
                >
                  <span className="bg-cta/15 text-foreground grid size-10 shrink-0 place-items-center rounded-lg">
                    <action.icon className="size-5" aria-hidden="true" />
                  </span>
                  <span className="flex-1">
                    <span className="block font-semibold">{action.label}</span>
                    <span className="text-muted-foreground text-xs">
                      {action.phase ? `Coming in phase ${action.phase}` : action.hint}
                    </span>
                  </span>
                  <ArrowRight
                    className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </Link>
              ))}
            </CardContent>
          </Card>
        </section>
        <div className="lg:col-span-2">
          {user.role === "admin" ? (
            <SystemHealthCard />
          ) : (
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="text-lg">Welcome</CardTitle>
                <CardDescription>
                  This is the new home for unit cards, work orders, sales and parts. Sections appear in the menu as
                  they're ready.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
