import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  ClipboardPlus,
  Database,
  DollarSign,
  FileText,
  FileUp,
  HardDriveDownload,
  type LucideIcon,
  PackageCheck,
  PackageMinus,
  ReceiptText,
  Timer,
  Truck,
  UserCheck,
  Wrench,
} from "lucide-react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { canSeeInvoices } from "@/features/parts/invoices/api";
import { useDashboard, useReports } from "@/features/reports/api";
import { canEditWorkOrders } from "@/features/service/api";
import { canEditUnits } from "@/features/units/permissions";
import { api } from "@/lib/api";
import { isOn, useFlags } from "@/lib/flags";
import { formatCents } from "@/lib/format";
import type { AdminHealth, DashboardTile } from "@/lib/types";
import { cn } from "@/lib/utils";

function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

const ICONS: Record<string, LucideIcon> = {
  "units-in-stock": Truck,
  "open-work-orders": Wrench,
  "my-work-orders": UserCheck,
  "maintenance-due": Activity,
  "open-quotes": FileText,
  "sales-this-month": DollarSign,
  "low-stock": PackageMinus,
  "parts-value": PackageCheck,
  "invoices-to-check": ReceiptText,
  "backorders": Timer,
};

type QuickAction = { label: string; icon: LucideIcon; to: string; hint: string };

function TileCard({ tile }: { tile: DashboardTile }) {
  const Icon = ICONS[tile.key] ?? ClipboardList;
  const warn = tile.tone === "warning";
  return (
    <Link to={tile.to} className="focus-visible:ring-ring rounded-xl focus-visible:ring-2 focus-visible:outline-none">
      <Card className={cn("hover:border-primary/40 h-full gap-3 py-5 transition-colors", warn && "border-warning/50")}>
        <CardContent className="flex flex-col gap-3 px-5">
          <span
            className={cn(
              "grid size-10 place-items-center rounded-xl",
              warn ? "bg-warning/15 text-warning" : "bg-primary/10 text-primary dark:bg-primary/15",
            )}
          >
            <Icon className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className={cn("font-extrabold tabular-nums", tile.kind === "money" ? "text-2xl" : "text-3xl", warn && "text-warning")}>
              {tile.kind === "money" ? formatCents(tile.value) : Number(tile.value).toLocaleString("en-US")}
            </p>
            <p className="text-sm font-semibold">{tile.label}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function ReportsCard() {
  const reports = useReports();
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <BarChart3 className="size-5" aria-hidden="true" /> Reports
        </CardTitle>
        <CardDescription>Totals for any dates, ready to download.</CardDescription>
      </CardHeader>
      <CardContent>
        {reports.isPending ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-6" />
            <Skeleton className="h-6" />
          </div>
        ) : (
          <ul className="divide-y">
            {(reports.data?.reports ?? []).map((r) => (
              <li key={r.key}>
                <Link to={`/reports/${r.key}`} className="hover:text-primary flex min-h-11 items-center justify-between gap-2 text-sm font-medium">
                  {r.title} <ArrowRight className="text-muted-foreground size-4" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

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

export function DashboardPage() {
  const user = useCurrentUser();
  const flags = useFlags();
  const dashboard = useDashboard();
  const on = (key: string) => isOn(flags.data?.flags, key);
  const actions: QuickAction[] = [];
  if (on("service") && canEditWorkOrders(user.role)) {
    actions.push({ label: "New work order", icon: ClipboardPlus, to: "/service/new", hint: "Open a job on a unit" });
  }
  if (on("customers-units")) {
    actions.push(
      canEditUnits(user.role)
        ? { label: "Add a unit", icon: Truck, to: "/units/new", hint: "Enter a unit card" }
        : { label: "Browse units", icon: Truck, to: "/units", hint: "Find a unit by serial or customer" },
    );
  }
  if (on("parts") && on("parts-invoices") && canSeeInvoices(user.role)) {
    actions.push({ label: "Receive a parts invoice", icon: PackageCheck, to: "/parts/invoices", hint: "Upload it, check it, receive it" });
  }
  if (on("batch-import") && ["admin", "sales", "service"].includes(user.role)) {
    actions.push({ label: "Import unit cards", icon: FileUp, to: "/imports/new", hint: "Upload a spreadsheet of cards" });
  }
  if (on("reports")) {
    actions.push({ label: "Reports", icon: BarChart3, to: "/reports", hint: "Totals for any dates, ready to download" });
  }
  const tiles = dashboard.data?.tiles;
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
        {dashboard.isError ? (
          <p className="text-destructive text-sm font-semibold">Couldn't load the numbers. They'll try again shortly.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-4" aria-busy={!tiles}>
            {tiles
              ? tiles.map((tile) => <TileCard key={tile.key} tile={tile} />)
              : Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-5">
        <section aria-labelledby="actions-heading" className="lg:col-span-3">
          <Card className="h-full">
            <CardHeader>
              <CardTitle id="actions-heading" className="text-lg">
                Quick actions
              </CardTitle>
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
                    <span className="text-muted-foreground text-xs">{action.hint}</span>
                  </span>
                  <ArrowRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </section>
        <div className="flex flex-col gap-6 lg:col-span-2">
          {user.role === "admin" && <SystemHealthCard />}
          {on("reports") && <ReportsCard />}
        </div>
      </div>
    </div>
  );
}
