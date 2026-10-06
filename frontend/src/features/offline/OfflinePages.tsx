import { ArrowLeft, Printer, RefreshCw, Search, Truck, WifiOff } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";

import { Logo } from "@/components/brand/Logo";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { SpecDetails } from "@/features/units/SpecCard";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";
import { type OfflineUnit, searchUnits, sortUnits } from "@/lib/offline/pack";
import { useOfflinePack, useOnline } from "@/lib/offline/sync";
import { cn } from "@/lib/utils";

function unitName(u: OfflineUnit) {
  return [u.year, u.make, u.model].filter(Boolean).join(" ") || "Unit";
}

function Layout({ children }: { children: ReactNode }) {
  const online = useOnline();
  const pack = useOfflinePack();
  return (
    <div className="min-h-dvh">
      <header className="bg-card/95 sticky top-0 z-20 border-b backdrop-blur print:hidden">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          <Logo compact />
          <span className="flex-1" />
          <ThemeToggle />
        </div>
      </header>
      <div role="status" className="bg-warning/15 border-warning/40 border-b print:hidden">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 text-sm">
          <WifiOff className="text-warning size-5 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1">
            <b>Saved copy.</b> {online ? "The system can't be reached right now." : "This device is offline."} You're looking at the copy saved on this device
            {pack.data ? ` on ${formatDateTime(pack.data.savedAt)}` : ""}. Nothing can be changed here.
          </span>
          <Button asChild variant="outline" size="sm">
            <a href="/">
              <RefreshCw className="size-4" /> Try the live system
            </a>
          </Button>
        </div>
      </div>
      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-6">{children}</main>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label="Loading">
      <Skeleton className="h-10" />
      <Skeleton className="h-40" />
    </div>
  );
}

function NothingSaved() {
  return (
    <Card className="py-0">
      <EmptyState
        title="Nothing saved on this device"
        message="When someone is signed in and online, the app keeps a copy of our stock and recently worked-on units here. Signing out wipes it."
      />
    </Card>
  );
}

export function OfflineListPage() {
  const pack = useOfflinePack();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "stock">("all");
  if (pack.isPending) return <Layout children={<Loading />} />;
  if (!pack.data) return <Layout children={<NothingSaved />} />;
  const all = pack.data.units;
  const units = sortUnits(searchUnits(all, q, scope));
  const stockCount = all.filter((u) => u.in_stock).length;
  return (
    <Layout>
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Units (saved copy)</h1>
        <p className="text-muted-foreground mt-1">
          {all.length} units: our stock and units worked on in the last 90 days, with their full spec cards.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            type="search"
            aria-label="Search saved units"
            placeholder="Serial, stock #, make, model or customer"
            className="pl-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <div role="tablist" aria-label="Which units" className="bg-muted inline-flex rounded-xl p-1">
          {(
            [
              ["all", `All (${all.length})`],
              ["stock", `Our stock (${stockCount})`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={scope === value}
              onClick={() => setScope(value)}
              className={cn(
                "min-h-10 flex-1 rounded-lg px-4 text-sm font-semibold whitespace-nowrap",
                scope === value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <Card className="gap-0 py-0">
        {units.length === 0 ? (
          <EmptyState title="No saved units match" message="Only stock and recently worked-on units are saved on this device." />
        ) : (
          <ul className="divide-y" aria-label="Saved units">
            {units.map((u) => (
              <li key={u.id}>
                <Link to={`/offline/units/${u.id}`} className="hover:bg-muted/60 flex items-center gap-3 p-4">
                  <span className="bg-primary/10 text-primary grid size-11 shrink-0 place-items-center rounded-xl">
                    <Truck className="size-5" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{unitName(u)}</span>
                    <span className="text-muted-foreground block truncate font-mono text-xs">
                      {[u.serial_number, u.stock_number && `Stock #${u.stock_number}`].filter(Boolean).join(" · ")}
                    </span>
                    <span className="text-muted-foreground block truncate text-sm">{u.in_stock ? "Our stock" : (u.owner_name ?? "")}</span>
                  </span>
                  {u.current_hours && <span className="text-sm font-semibold whitespace-nowrap tabular-nums">{formatNumber(u.current_hours)} h</span>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Layout>
  );
}

export function OfflineUnitPage() {
  const { id = "" } = useParams();
  const pack = useOfflinePack();
  if (pack.isPending) return <Layout children={<Loading />} />;
  if (!pack.data) return <Layout children={<NothingSaved />} />;
  const u = pack.data.units.find((x) => x.id === id);
  if (!u) {
    return (
      <Layout>
        <EmptyState
          title="This unit isn't in the saved copy"
          message="Only stock and recently worked-on units are saved on this device."
          action={
            <Button asChild variant="outline">
              <Link to="/offline">Saved units</Link>
            </Button>
          }
        />
      </Layout>
    );
  }
  return (
    <Layout>
      <div className="print:hidden">
        <Link to="/offline" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Saved units
        </Link>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap gap-2">
            {u.in_stock && <Badge variant="outline">Our stock</Badge>}
            <Badge variant="outline">{u.condition === "new" ? "New" : "Used"}</Badge>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{unitName(u)}</h1>
          <p className="text-muted-foreground font-mono">{u.serial_number}</p>
        </div>
        <Button variant="outline" className="print:hidden" onClick={() => window.print()}>
          <Printer className="size-4" /> Print
        </Button>
      </div>
      <dl className="bg-card grid grid-cols-2 gap-4 rounded-xl border p-5 sm:grid-cols-4">
        {(
          [
            ["Owner", u.in_stock ? "Our stock" : (u.owner_name ?? "—")],
            ["Hours", u.current_hours ? `${formatNumber(u.current_hours)} h${u.current_hours_date ? ` (${formatDate(u.current_hours_date)})` : ""}` : "—"],
            ["Stock #", u.stock_number || "—"],
            ["Capacity", u.capacity_lbs ? `${u.capacity_lbs.toLocaleString()} lb` : "—"],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{label}</dt>
            <dd className="text-base font-bold break-words sm:text-lg">{value}</dd>
          </div>
        ))}
      </dl>
      {(u.special_equipment || u.field_modifications || u.notes) && (
        <div className="bg-card flex flex-col gap-3 rounded-xl border p-5 text-sm">
          {(
            [
              ["Special equipment", u.special_equipment],
              ["Field modifications", u.field_modifications],
              ["Notes", u.notes],
            ] as const
          )
            .filter(([, v]) => v)
            .map(([label, v]) => (
              <div key={label}>
                <h2 className="font-semibold">{label}</h2>
                <p className="text-muted-foreground whitespace-pre-line">{v}</p>
              </div>
            ))}
        </div>
      )}
      <SpecDetails unit={{ ...u, cost: null, asking_price: null, sale_price: null }} />
    </Layout>
  );
}
