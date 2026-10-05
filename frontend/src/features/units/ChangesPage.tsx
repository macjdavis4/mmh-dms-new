import type { ColumnDef } from "@tanstack/react-table";
import { ArrowRight, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { Field, NativeSelect } from "@/components/form/Field";
import { PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate, formatMoney, formatNumber } from "@/lib/format";
import type { UnitChange, UnitChangeTotals } from "@/lib/types";
import { cn } from "@/lib/utils";

import { type ChangeFilters, changeParams, EMPTY_CHANGE_FILTERS, useUnitChanges } from "./api";
import { REASON_LABELS, reasonsFor } from "./changeHands";
import { DealMoney, ReasonBadge } from "./OwnershipTimeline";
import { canSeePricing } from "./permissions";

const PAGE_SIZE = 50;
const DIRECTIONS: { value: ChangeFilters["direction"]; label: string }[] = [
  { value: "", label: "All" },
  { value: "out", label: "Sold" },
  { value: "in", label: "Came back" },
  { value: "between", label: "Between customers" },
];

function readFilters(params: URLSearchParams): ChangeFilters {
  const f = { ...EMPTY_CHANGE_FILTERS };
  for (const key of Object.keys(f) as (keyof ChangeFilters)[]) {
    const value = params.get(key);
    if (value !== null) (f as Record<string, string>)[key] = value;
  }
  if (!DIRECTIONS.some((d) => d.value === f.direction)) f.direction = "";
  return f;
}

function reasonOptions(direction: ChangeFilters["direction"]) {
  if (direction) return reasonsFor(direction);
  return Object.entries(REASON_LABELS).map(([value, label]) => ({ value, label }));
}

const unitName = (c: UnitChange) => [c.unit_make, c.unit_model].filter(Boolean).join(" ") || "Unit";
const dealKind = (c: UnitChange) => (c.owner_kind === "dealer" ? "purchase" : c.from_kind === "dealer" ? "sale" : null);

function Party({ label, customer }: { label: string; customer: string | null }) {
  return customer ? (
    <Link to={`/customers/${customer}`} className="text-primary hover:underline">
      {label}
    </Link>
  ) : (
    <span>{label === "Maine Material Handling stock" ? "Our stock" : label}</span>
  );
}

function FromTo({ c }: { c: UnitChange }) {
  return (
    <span className="flex flex-wrap items-center gap-x-1.5">
      <Party label={c.from_label} customer={c.from_customer} />
      <ArrowRight className="text-muted-foreground size-3.5 shrink-0" aria-label="to" />
      <Party label={c.owner_label} customer={c.customer} />
    </span>
  );
}

function ChangeCard({ c, pricing }: { c: UnitChange; pricing: boolean }) {
  const kind = dealKind(c);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="flex items-start justify-between gap-3">
        <Link to={`/units/${c.unit}`} className="text-primary font-semibold hover:underline">
          {unitName(c)}
        </Link>
        <ReasonBadge reason={c.reason} label={c.reason_label || "Changed owner"} />
      </span>
      <span className="text-sm">
        <FromTo c={c} />
      </span>
      {pricing && kind && (
        <span className="text-sm font-medium">
          <DealMoney price={c.price} cost={c.cost} kind={kind} />
        </span>
      )}
      <span className="text-muted-foreground flex flex-wrap gap-x-3 gap-y-1 text-xs">
        <span>{formatDate(c.start_date)}</span>
        {c.unit_serial && <span className="font-mono">{c.unit_serial}</span>}
        {c.reference && <span>Ref {c.reference}</span>}
        {c.hours !== null && <span>{formatNumber(c.hours)} h</span>}
      </span>
    </div>
  );
}

function Tile({ label, count, lines }: { label: string; count: number | undefined; lines: string[] }) {
  return (
    <div className="bg-card flex flex-col rounded-xl border p-4">
      <span className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">{label}</span>
      <span className="text-3xl font-extrabold tabular-nums">{count ?? "—"}</span>
      {lines.map((line) => (
        <span key={line} className="text-muted-foreground text-sm">
          {line}
        </span>
      ))}
    </div>
  );
}

function Totals({ totals, pricing }: { totals: UnitChangeTotals | undefined; pricing: boolean }) {
  const sold = totals?.sold;
  const back = totals?.came_back;
  const soldLines =
    pricing && sold?.total
      ? [
          `${formatMoney(sold.total)} in sales`,
          ...(sold.margin && sold.with_margin
            ? [`${formatMoney(sold.margin)} margin${sold.with_margin < sold.count ? ` on ${sold.with_margin} with a cost` : ""}`]
            : []),
        ]
      : [];
  return (
    <div className="mb-4 grid gap-3 sm:grid-cols-3" aria-label="Totals for these filters">
      <Tile label="Sold" count={sold?.count} lines={soldLines} />
      <Tile label="Came back to stock" count={back?.count} lines={pricing && back?.total ? [`${formatMoney(back.total)} paid`] : []} />
      <Tile label="Between customers" count={totals?.between_customers.count} lines={[]} />
    </div>
  );
}

export function ChangesPage() {
  const user = useCurrentUser();
  const pricing = canSeePricing(user.role);
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const [page, setPage] = useState(1);
  const { list, totals } = useUnitChanges(filters, page, PAGE_SIZE);
  const update = (patch: Partial<ChangeFilters>) => {
    setParams(changeParams({ ...filters, ...patch }), { replace: true });
    setPage(1);
  };
  const filtered = JSON.stringify(filters) !== JSON.stringify(EMPTY_CHANGE_FILTERS);

  const columns = useMemo<ColumnDef<UnitChange>[]>(
    () => [
      { id: "date", header: "Date", cell: ({ row }) => <span className="whitespace-nowrap">{formatDate(row.original.start_date)}</span> },
      {
        id: "unit",
        header: "Unit",
        cell: ({ row }) => (
          <span>
            <Link to={`/units/${row.original.unit}`} className="text-primary block font-semibold hover:underline">
              {unitName(row.original)}
            </Link>
            <span className="text-muted-foreground font-mono text-xs">
              {[row.original.unit_serial, row.original.unit_stock_number].filter(Boolean).join(" · ")}
            </span>
          </span>
        ),
      },
      {
        id: "why",
        header: "Why",
        cell: ({ row }) => <ReasonBadge reason={row.original.reason} label={row.original.reason_label || "Changed owner"} />,
      },
      { id: "from-to", header: "From → to", cell: ({ row }) => <FromTo c={row.original} /> },
      ...(pricing
        ? [
            {
              id: "money",
              header: "Deal",
              cell: ({ row }) => {
                const kind = dealKind(row.original);
                return kind ? <DealMoney price={row.original.price} cost={row.original.cost} kind={kind} /> : "—";
              },
            } satisfies ColumnDef<UnitChange>,
          ]
        : []),
      {
        id: "ref",
        header: "Ref / hours",
        cell: ({ row }) => (
          <span className="text-muted-foreground flex flex-col text-sm">
            <span>{row.original.reference || "—"}</span>
            {row.original.hours !== null && <span>{formatNumber(row.original.hours)} h</span>}
          </span>
        ),
      },
    ],
    [pricing],
  );
  const total = list.data?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Bought and sold"
        description="Every unit that changed hands: sales, trade-ins, repossessions, buy-backs and lease returns. Each deal keeps its own numbers."
      />
      <Totals totals={totals.data} pricing={pricing} />
      <div className="mb-4 flex flex-col gap-3">
        <div role="tablist" aria-label="Which changes" className="bg-muted flex w-full overflow-x-auto rounded-xl p-1 sm:inline-flex sm:w-auto sm:self-start">
          {DIRECTIONS.map((d) => (
            <button
              key={d.value || "all"}
              role="tab"
              type="button"
              aria-selected={filters.direction === d.value}
              onClick={() => update({ direction: d.value, reason: "" })}
              className={cn(
                "min-h-10 flex-1 rounded-lg px-3 text-sm font-semibold whitespace-nowrap transition-colors sm:flex-none sm:px-4",
                filters.direction === d.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {d.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
          <div className="col-span-2 lg:col-span-1">
            <Label htmlFor="changes-search" className="mb-1.5 block text-sm font-semibold">
              Search
            </Label>
            <Input
              id="changes-search"
              type="search"
              placeholder="Serial, stock #, make, model, customer or invoice #"
              value={filters.q}
              onChange={(e) => update({ q: e.target.value })}
            />
          </div>
          <Field id="changes-reason" label="Why" className="col-span-2 lg:col-span-1">
            <NativeSelect
              id="changes-reason"
              value={filters.reason}
              onChange={(v) => update({ reason: v })}
              options={reasonOptions(filters.direction)}
              placeholder="Any reason"
            />
          </Field>
          <Field id="changes-from" label="From">
            <Input id="changes-from" type="date" value={filters.date_from} onChange={(e) => update({ date_from: e.target.value })} />
          </Field>
          <Field id="changes-to" label="To">
            <Input id="changes-to" type="date" value={filters.date_to} onChange={(e) => update({ date_to: e.target.value })} />
          </Field>
          {filtered && (
            <Button variant="ghost" className="col-span-2 justify-self-start lg:col-span-1" onClick={() => update(EMPTY_CHANGE_FILTERS)}>
              <X className="size-4" /> Clear
            </Button>
          )}
        </div>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="Units that changed hands"
          tableFrom="lg"
          columns={columns}
          data={list.data?.results}
          isLoading={list.isPending}
          error={list.error}
          onRetry={() => void list.refetch()}
          getRowId={(c) => c.id}
          renderCard={(row) => <ChangeCard c={row.original} pricing={pricing} />}
          empty={{
            title: filtered ? "Nothing matches" : "No units have changed hands yet",
            message: filtered
              ? "Try a different search or dates."
              : "Sales, trade-ins and repossessions show up here when they're recorded with Change owner on a unit's page.",
          }}
        />
      </Card>
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-sm">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(page + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </>
  );
}
